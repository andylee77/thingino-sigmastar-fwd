"""Test registry, the device context (feature discovery), the per-test API and
the runner. Tests live in t_*.py and register with @test."""
from __future__ import annotations

import fnmatch
import time
import traceback
from dataclasses import dataclass, field

from .schema import SpecValidator, ZeepView
from .soap import NS, NS_TO_SERVICE, SERVICES, Client, Reply, local, xp, xt

SERVICE_KEYS = set(SERVICES)

# test categories, by what they do to the camera
READ = "read"          # queries only
SESSION = "session"    # temporary server state it cleans up (event subscriptions)
CONFIG = "config"      # Set* calls, restored afterwards; --allow-config
MOVE = "move"          # PTZ or focus motion; --allow-move and a MAC match
PRESET = "preset"      # writes a preset slot; --allow-preset-write
CATS = (READ, SESSION, CONFIG, MOVE, PRESET)

PASS, WARN, FAIL, ERROR, NA, SKIP = "PASS", "WARN", "FAIL", "ERROR", "N/A", "SKIP"
RANK = {PASS: 0, WARN: 1, FAIL: 2, ERROR: 3}

SPACES = "http://www.onvif.org/ver10/tptz/"
FOV_SPACE = SPACES + "PanTiltSpaces/TranslationSpaceFov"


@dataclass
class Test:
    id: str
    title: str
    service: str
    fn: object
    cat: str = READ
    needs: tuple = ()
    clients: tuple = ()     # frigate, ha, go2rtc: the clients that rely on it
    profiles: tuple = ()    # S, T, M, G: profiles whose devices must pass it
    ref: str = ""           # spec / test-spec reference

    @property
    def official(self):
        return not self.id.startswith("X-")


TESTS: list[Test] = []


def test(id, title, service, cat=READ, needs=(), clients=(), profiles=(), ref=""):
    def deco(fn):
        TESTS.append(Test(id, title, service, fn, cat, tuple(needs), tuple(clients),
                          tuple(profiles), ref))
        return fn
    return deco


class Abort(Exception):
    pass


class NotApplicable(Exception):
    pass


@dataclass
class Result:
    test: Test
    status: str = PASS
    messages: list = field(default_factory=list)
    duration: float = 0.0
    calls: int = 0
    schema: list = field(default_factory=list)    # XSD errors
    lost: list = field(default_factory=list)      # elements the zeep clients skip
    ops: list = field(default_factory=list)       # "service:Operation" exercised


class Run:
    """What a test function gets."""

    def __init__(self, ctx, result: Result):
        self.ctx, self.r = ctx, result
        self.c = ctx.client
        self.d = ctx.data
        self.f = ctx.features

    # -------------------------------------------------------------- status
    def _bump(self, status):
        if RANK.get(status, 0) > RANK.get(self.r.status, 0):
            self.r.status = status

    def info(self, msg):
        self.r.messages.append(msg)

    def warn(self, msg):
        self.r.messages.append("WARN " + msg)
        self._bump(WARN)

    def check(self, cond, msg, else_warn=False):
        """Soft assertion: records a FAIL (or WARN) and carries on."""
        if not cond:
            self.r.messages.append(("WARN " if else_warn else "FAIL ") + msg)
            self._bump(WARN if else_warn else FAIL)
        return bool(cond)

    def fail(self, msg):
        self.r.messages.append("FAIL " + msg)
        self._bump(FAIL)
        raise Abort(msg)

    def na(self, msg):
        raise NotApplicable(msg)

    # -------------------------------------------------------------- calls
    def call(self, service, op, inner="", **kw) -> Reply:
        rep = self.c.call(service, op, inner, **kw)
        self.r.calls += 1
        svc = service if service in SERVICE_KEYS else {NS["wsnt"]: "events"}.get(service, str(service))
        key = f"{svc}:{op}"
        if key not in self.r.ops:
            self.r.ops.append(key)
        if rep.ok and not kw.get("raw"):
            self._inspect(rep)
        return rep

    def _inspect(self, rep):
        v = self.ctx.validator
        if v is not None:
            errs = v.validate(rep.body)
            for e in errs or []:
                m = f"{local(rep.body.tag)}: {e}"
                if m not in self.r.schema:
                    self.r.schema.append(m)
        z = self.ctx.zeep
        if z is not None and z.ok:
            lost = z.lost(rep.body)
            for p in lost or []:
                m = f"{local(rep.body.tag)}: {p}"
                if m not in self.r.lost:
                    self.r.lost.append(m)

    def ok(self, service, op, inner="", what=None, **kw) -> Reply:
        """Call and require success (aborts the test otherwise)."""
        rep = self.call(service, op, inner, **kw)
        if not rep.ok:
            self.fail(f"{what or op}: {rep.why()}")
        return rep

    def expect_fault(self, rep: Reply, *subcodes, what=None):
        """A SOAP fault is required; the named ter: subcodes are what the
        spec asks for (another subcode is a WARN)."""
        w = what or rep.op
        if rep.ok:
            self.r.messages.append(f"FAIL {w}: accepted, a SOAP fault was expected")
            self._bump(FAIL)
            return False
        if rep.fault is None:
            self.check(False, f"{w}: no SOAP fault, {rep.why()}")
            return False
        if subcodes and not rep.fault.has(*subcodes):
            self.warn(f"{w}: fault {rep.fault}, spec expects {'/'.join(subcodes)}")
        else:
            self.info(f"{w}: fault {rep.fault}")
        if rep.status not in (400, 500):
            self.warn(f"{w}: fault came with HTTP {rep.status} (SOAP 1.2 HTTP binding: 400 or 500)")
        return True


# ------------------------------------------------------------------ context
class Context:
    def __init__(self, host, port, user, password, *, auth="wsse", timeout=10.0,
                 allow=(READ, SESSION), expect_mac=None, name=None, validate=True,
                 strict_schema=False, args=None):
        self.client = Client(host, port, user, password, timeout=timeout, auth=auth)
        self.host, self.port, self.user, self.password = host, port, user, password
        self.allow = set(allow)
        self.expect_mac = (expect_mac or "").lower().replace("-", ":")
        self.name = name or host
        self.args = args
        self.strict_schema = strict_schema
        self.validator = SpecValidator() if validate else None
        self.zeep = ZeepView() if validate else None
        self.features: dict = {}
        self.data: dict = {}
        self.notes: list = []
        self.mac_ok = None

    # every discovery step tolerates failure; tests then see the gap
    def discover(self):
        c, d, f = self.client, self.data, self.features
        r = c.call("device", "GetSystemDateAndTime", auth="none")
        if r.ok:
            dev = _utc(r.body)
            if dev:
                import datetime as dt
                c.time_offset = (dev - dt.datetime.now(dt.timezone.utc)).total_seconds()
            d["time_offset"] = c.time_offset
        else:
            self.notes.append(f"GetSystemDateAndTime: {r.why()}")
        r = c.call("device", "GetServices", "<IncludeCapability>true</IncludeCapability>")
        d["services"] = {}
        if r.ok:
            for s in r.x("tds:Service"):
                ns = xt(s, "tds:Namespace", "")
                key = NS_TO_SERVICE.get(ns)
                addr = xt(s, "tds:XAddr", "")
                ver = f'{xt(s, "tds:Version/tt:Major", "?")}.{xt(s, "tds:Version/tt:Minor", "?")}'
                d["services"][ns] = {"xaddr": addr, "version": ver, "key": key,
                                     "caps": s.find(f"{{{NS['tds']}}}Capabilities")}
                if key and addr:
                    c.xaddr[key] = _rehost(addr, self.host)
        else:
            self.notes.append(f"GetServices: {r.why()}")
        r = c.call("device", "GetCapabilities", "<Category>All</Category>")
        d["capabilities_ok"] = r.ok
        if r.ok:
            for key, tag in (("media", "Media"), ("ptz", "PTZ"), ("imaging", "Imaging"),
                             ("events", "Events"), ("analytics", "Analytics")):
                a = r.t(f"tds:Capabilities/tt:{tag}/tt:XAddr")
                if a and key not in c.xaddr:
                    c.xaddr[key] = _rehost(a, self.host)
            d["caps_xml"] = r.body
        for k in ("device", "media", "media2", "ptz", "imaging", "events", "deviceio", "analytics"):
            f[f"svc.{k}"] = k in c.xaddr or k == "device"
        r = c.call("device", "GetDeviceInformation")
        if r.ok:
            d["info"] = {local(e.tag): (e.text or "").strip() for e in r.body}
        r = c.call("device", "GetNetworkInterfaces")
        d["macs"] = [m.lower() for m in r.x(".//tt:HwAddress/text()")] if r.ok else []
        if self.expect_mac:
            self.mac_ok = any(m.endswith(self.expect_mac) or m == self.expect_mac for m in d["macs"])
        r = c.call("device", "GetScopes")
        d["scopes"] = [s for s in r.x(".//tt:ScopeItem/text()")] if r.ok else []
        for s in d["scopes"]:
            if s.startswith("onvif://www.onvif.org/Profile/"):
                p = s.rsplit("/", 1)[-1]
                f["claims." + ("S" if p == "Streaming" else p)] = True
        self._media()
        if f["svc.media2"]:
            self._media2()
        if f["svc.ptz"]:
            self._ptz()
        if f["svc.imaging"]:
            self._imaging()
        if f["svc.events"]:
            r = c.call("events", "GetServiceCapabilities")
            cap = r.x("tev:Capabilities")
            if cap:
                f["events.pullpoint"] = cap[0].get("WSPullPointSupport") in ("true", "1")
                f["events.basic"] = True
                d["events_caps"] = dict(cap[0].attrib)
            else:
                f["events.basic"] = True
        if f["svc.deviceio"]:
            r = c.call("deviceio", "GetRelayOutputs")
            d["relays"] = r.x("tmd:RelayOutputs/@token") if r.ok else []
        if not d.get("relays"):
            r = c.call("device", "GetRelayOutputs")
            d["relays"] = r.x("tds:RelayOutputs/@token") if r.ok else []
        f["relays"] = bool(d["relays"])

    def _media(self):
        c, d, f = self.client, self.data, self.features
        r = c.call("media", "GetProfiles")
        d["profiles"] = []
        if not r.ok:
            self.notes.append(f"Media GetProfiles: {r.why()}")
            return
        for p in r.x("trt:Profiles"):
            ve = xp(p, "tt:VideoEncoderConfiguration")
            d["profiles"].append({
                "token": p.get("token"), "fixed": p.get("fixed"),
                "name": xt(p, "tt:Name", ""),
                "vsc": xt(p, "tt:VideoSourceConfiguration/@token"),
                "vs": xt(p, "tt:VideoSourceConfiguration/tt:SourceToken"),
                "venc": xt(p, "tt:VideoEncoderConfiguration/@token"),
                "encoding": xt(p, "tt:VideoEncoderConfiguration/tt:Encoding"),
                "width": int(xt(p, "tt:VideoEncoderConfiguration/tt:Resolution/tt:Width", "0") or 0),
                "height": int(xt(p, "tt:VideoEncoderConfiguration/tt:Resolution/tt:Height", "0") or 0),
                "fps": xt(p, "tt:VideoEncoderConfiguration/tt:RateControl/tt:FrameRateLimit"),
                "ptz": xt(p, "tt:PTZConfiguration/@token"),
                "aenc": xt(p, "tt:AudioEncoderConfiguration/tt:Encoding"),
                "aout": bool(xp(p, "tt:Extension/tt:AudioOutputConfiguration")),
                "has_venc": bool(ve),
            })
        f["media.profiles"] = bool(d["profiles"])
        f["audio"] = any(p["aenc"] for p in d["profiles"])
        f["backchannel"] = any(p["aout"] for p in d["profiles"])
        ptzp = [p for p in d["profiles"] if p["ptz"]]
        d["ptz_profile"] = (ptzp[0]["token"] if ptzp else None)
        d["vs_token"] = next((p["vs"] for p in d["profiles"] if p["vs"]), None)
        r = c.call("media", "GetServiceCapabilities")
        if r.ok:
            cap = r.x("trt:Capabilities")
            d["media_caps"] = dict(cap[0].attrib) if cap else {}
            f["snapshot"] = d["media_caps"].get("SnapshotUri") in ("true", "1")

    def _media2(self):
        c, d = self.client, self.data
        r = c.call("media2", "GetProfiles", "<Type>All</Type>")
        d["profiles2"] = []
        if r.ok:
            for p in r.x("tr2:Profiles"):
                d["profiles2"].append({
                    "token": p.get("token"),
                    "encoding": xt(p, "tr2:Configurations/tr2:VideoEncoder/tt:Encoding"),
                    "ptz": xt(p, "tr2:Configurations/tr2:PTZ/@token"),
                })
        self.features["media2.profiles"] = bool(d["profiles2"])

    def _ptz(self):
        c, d, f = self.client, self.data, self.features
        r = c.call("ptz", "GetServiceCapabilities")
        cap = r.x("tptz:Capabilities") if r.ok else []
        d["ptz_caps"] = dict(cap[0].attrib) if cap else {}
        for k in ("MoveStatus", "StatusPosition", "EFlip", "Reverse", "GetCompatibleConfigurations",
                  "MoveAndTrack"):
            f[f"ptz.cap.{k}"] = d["ptz_caps"].get(k) in ("true", "1")
        r = c.call("ptz", "GetNodes")
        d["ptz_nodes"] = []
        for n in (r.x("tptz:PTZNode") if r.ok else []):
            sp = {}
            for kind in ("AbsolutePanTiltPositionSpace", "AbsoluteZoomPositionSpace",
                         "RelativePanTiltTranslationSpace", "RelativeZoomTranslationSpace",
                         "ContinuousPanTiltVelocitySpace", "ContinuousZoomVelocitySpace",
                         "PanTiltSpeedSpace", "ZoomSpeedSpace"):
                sp[kind] = [{"uri": xt(s, "tt:URI", ""),
                             "x": (_f(xt(s, "tt:XRange/tt:Min")), _f(xt(s, "tt:XRange/tt:Max"))),
                             "y": (_f(xt(s, "tt:YRange/tt:Min")), _f(xt(s, "tt:YRange/tt:Max")))}
                            for s in xp(n, f"tt:SupportedPTZSpaces/tt:{kind}")]
            d["ptz_nodes"].append({
                "token": n.get("token"), "fixed_home": n.get("FixedHomePosition"),
                "name": xt(n, "tt:Name", ""), "spaces": sp,
                "max_presets": int(xt(n, "tt:MaximumNumberOfPresets", "0") or 0),
                "home": xt(n, "tt:HomeSupported") in ("true", "1"),
                "aux": [a.text for a in xp(n, "tt:AuxiliaryCommands") if a.text],
            })
        f["ptz"] = bool(d["ptz_nodes"]) and bool(d.get("ptz_profile"))
        n = d["ptz_nodes"][0] if d["ptz_nodes"] else {"spaces": {}}
        sp = n["spaces"]
        f["ptz.abs.pt"] = bool(sp.get("AbsolutePanTiltPositionSpace"))
        f["ptz.abs.zoom"] = bool(sp.get("AbsoluteZoomPositionSpace"))
        f["ptz.rel.pt"] = bool(sp.get("RelativePanTiltTranslationSpace"))
        f["ptz.rel.pt.fov"] = any(s["uri"] == FOV_SPACE for s in sp.get("RelativePanTiltTranslationSpace", []))
        f["ptz.rel.zoom"] = bool(sp.get("RelativeZoomTranslationSpace"))
        f["ptz.cont.pt"] = bool(sp.get("ContinuousPanTiltVelocitySpace"))
        f["ptz.cont.zoom"] = bool(sp.get("ContinuousZoomVelocitySpace"))
        f["ptz.home"] = bool(n.get("home"))
        f["ptz.presets"] = n.get("max_presets", 0) > 0
        f["ptz.aux"] = bool(n.get("aux"))
        r = c.call("ptz", "GetConfigurations")
        d["ptz_cfgs"] = []
        for cfg in (r.x("tptz:PTZConfiguration") if r.ok else []):
            d["ptz_cfgs"].append({
                "token": cfg.get("token"), "node": xt(cfg, "tt:NodeToken"),
                "defaults": {local(e.tag): (e.text or "").strip() for e in cfg
                             if local(e.tag).startswith("Default") and (e.text or "").strip()},
                "order": [local(e.tag) for e in cfg],
            })

    def _imaging(self):
        c, d, f = self.client, self.data, self.features
        vs = d.get("vs_token")
        if not vs:
            return
        r = c.call("imaging", "GetMoveOptions", f"<VideoSourceToken>{vs}</VideoSourceToken>")
        mo = r.x("timg:MoveOptions") if r.ok else []
        f["imaging.focus"] = bool(mo and len(mo[0]))
        for k in ("Absolute", "Relative", "Continuous"):
            f[f"imaging.focus.{k.lower()}"] = bool(mo and xp(mo[0], f"tt:{k}"))
        r = c.call("imaging", "GetOptions", f"<VideoSourceToken>{vs}</VideoSourceToken>")
        f["imaging.options"] = r.ok

    # -------------------------------------------------------------- running
    def select(self, only=None, skip=None, suites=None, clients=None):
        out = []
        for t in TESTS:
            if suites and t.service not in suites:
                continue
            if clients and not (set(clients) & set(t.clients)):
                continue
            if only and not any(fnmatch.fnmatch(t.id, p) for p in only):
                continue
            if skip and any(fnmatch.fnmatch(t.id, p) for p in skip):
                continue
            out.append(t)
        return out

    def run(self, tests, on_result=None):
        results = []
        for t in tests:
            r = Result(t)
            why = self._gate(t)
            if why:
                r.status, r.messages = why
            else:
                run = Run(self, r)
                t0 = time.monotonic()
                try:
                    t.fn(run)
                except Abort:
                    pass
                except NotApplicable as e:
                    r.status, r.messages = NA, [str(e)]
                except Exception as e:  # noqa: BLE001
                    r.status = ERROR
                    tb = traceback.format_exc().strip().splitlines()
                    r.messages.append(f"{type(e).__name__}: {e} ({tb[-3].strip() if len(tb) > 2 else ''})")
                r.duration = time.monotonic() - t0
                if r.status in (PASS, WARN):
                    if r.schema:
                        if self.strict_schema:
                            r.status = FAIL
                        elif r.status == PASS:
                            r.status = WARN
                    if r.lost and r.status == PASS:
                        r.status = WARN
            results.append(r)
            if on_result:
                on_result(r)
        return results

    def _gate(self, t):
        if t.cat not in self.allow:
            flag = {CONFIG: "--allow-config", MOVE: "--allow-move", PRESET: "--allow-preset-write"}.get(t.cat, "")
            return SKIP, [f"{t.cat} test; needs {flag}"]
        if t.cat in (MOVE, PRESET, CONFIG) and self.mac_ok is not True:
            return SKIP, ["writes or moves: needs --cam NAME or --mac matching the camera's MAC"
                          + ("" if self.mac_ok is None else " (MAC mismatch!)")]
        missing = [n for n in t.needs if not self.features.get(n)]
        if missing:
            return NA, ["device lacks: " + ", ".join(missing)]
        return None


def _f(s):
    try:
        return float(s)
    except (TypeError, ValueError):
        return None


def _utc(body):
    import datetime as dt
    u = xp(body, ".//tt:UTCDateTime")
    if not u:
        return None
    g = lambda p: int(xt(u[0], p, "0") or 0)  # noqa: E731
    try:
        return dt.datetime(g("tt:Date/tt:Year"), g("tt:Date/tt:Month"), g("tt:Date/tt:Day"),
                           g("tt:Time/tt:Hour"), g("tt:Time/tt:Minute"), g("tt:Time/tt:Second"),
                           tzinfo=dt.timezone.utc)
    except ValueError:
        return None


def _rehost(addr, host):
    """Keep the advertised path and port but the host we reached (cameras
    behind NAT or with a stale IP still advertise their own address)."""
    from urllib.parse import urlsplit, urlunsplit
    u = urlsplit(addr)
    if not u.hostname:
        return addr
    netloc = host + (f":{u.port}" if u.port else "")
    return urlunsplit((u.scheme, netloc, u.path, u.query, ""))
