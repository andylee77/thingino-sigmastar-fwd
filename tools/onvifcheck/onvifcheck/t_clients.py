"""Client emulation: what Frigate, Home Assistant and go2rtc make of the
camera. The raw-SOAP tests elsewhere say what the camera sends; these replay
each client's own logic, through onvif-zeep-async (Frigate 0.17.2 pins
4.0.*; requirements.txt pins 4.0.4), so a PASS predicts the client's behaviour.

Sources, read at the tags named:
Frigate v0.17.2 frigate/ptz/onvif.py (_init_onvif, get_camera_status) and
frigate/ptz/autotrack.py (_autotracker_setup, calibration); Home Assistant
2026.11.0 homeassistant/components/onvif; go2rtc v1.9.10 pkg/onvif."""
from __future__ import annotations

import asyncio
import math
import os
import re
import statistics
import time

from .core import FOV_SPACE, MOVE, SPACES, test
from .soap import NS

LIB_SERVICES = ("media", "ptz", "imaging", "events", "deviceio", "analytics")
TGEN_ZOOM = SPACES + "ZoomSpaces/TranslationGenericSpace"


def _lib():
    try:
        import onvif
        from onvif import ONVIFCamera
    except ImportError:
        return None, None
    return ONVIFCamera, os.path.join(os.path.dirname(onvif.__file__), "wsdl")


def _need_lib(r):
    if _lib()[0] is None:
        r.na("onvif-zeep-async not installed")


async def _connect(r):
    ONVIFCamera, wsdl = _lib()
    cam = ONVIFCamera(r.ctx.host, r.ctx.port, r.ctx.user, r.ctx.password, wsdl_dir=wsdl)
    await cam.update_xaddrs()
    return cam


def _lib_version():
    import onvif
    try:
        return open(os.path.join(os.path.dirname(onvif.__file__), "version.txt")).read().strip()
    except OSError:
        return "?"


@test("X-LIB-XADDRS", "onvif-zeep-async finds every service the camera offers", "clients",
      clients=("frigate", "ha"), ref="onvif-zeep-async 4.0 update_xaddrs: GetCapabilities only")
def t_xaddrs(r):
    _need_lib(r)

    async def go():
        cam = await _connect(r)
        try:
            seen = {}
            for name in LIB_SERVICES:
                try:
                    await getattr(cam, f"create_{name}_service")()
                    seen[name] = True
                except Exception as e:  # noqa: BLE001
                    seen[name] = str(e)[:120]
            return seen
        finally:
            await cam.close()
    seen = asyncio.run(go())
    r.info(f"onvif-zeep-async {_lib_version()}")
    for name in LIB_SERVICES:
        offered = r.f.get(f"svc.{name}")
        if offered and seen.get(name) is not True:
            if name == "deviceio":
                # 4.0 reads XAddrs only from GetCapabilities' top-level entries, and
                # the schema puts DeviceIO inside Extension: no camera can fix this
                r.info("deviceio: offered, but onvif-zeep-async 4.0 never reads DeviceIO from "
                       "GetCapabilities (it sits in Extension); a library limit, not a camera fault. "
                       "4.3 (HA, Frigate dev) asks GetServices")
                continue
            hint = {"imaging": " Frigate logs 'Imaging service not supported' and shows no focus control",
                    "ptz": " no PTZ in Frigate"}.get(name, "")
            r.check(False, f"{name}: offered (GetServices) but the library cannot use it;{hint}")
        elif seen.get(name) is True:
            r.info(f"{name}: usable")


# ------------------------------------------------------------------ Frigate
async def _frigate_init(r):
    """Frigate 0.17.2 _init_onvif, as far as it touches the camera, minus the
    commands. Returns a dict of what Frigate would conclude."""
    cam = await _connect(r)
    out = {"log": [], "features": []}
    try:
        try:
            ptz = await cam.create_ptz_service()
        except Exception as e:  # noqa: BLE001
            out["fatal"] = f"Unable to get Onvif capabilities for camera: {e}"
            return out
        media = await cam.create_media_service()
        profiles = await media.GetProfiles()
        prof = None
        for p in profiles:
            if not p.VideoEncoderConfiguration or not p.PTZConfiguration:
                continue
            c = p.PTZConfiguration
            if c.DefaultContinuousPanTiltVelocitySpace is not None or \
                    c.DefaultContinuousZoomVelocitySpace is not None:
                prof = p
                break
        if prof is None:
            out["fatal"] = "No appropriate Onvif profiles found for camera"
            return out
        out["profile"] = prof.token
        c = prof.PTZConfiguration
        try:
            await cam.create_imaging_service()
            out["imaging"] = True
        except Exception as e:  # noqa: BLE001
            out["imaging"] = False
            out["log"].append(f"DEBUG Imaging service not supported: {e}")
        vs = await media.GetVideoSources()
        out["vs"] = vs[0].token if vs else None
        opts = await ptz.GetConfigurationOptions({"ConfigurationToken": c.token})
        out["opts"] = opts
        fov = None
        for s in (opts.Spaces.RelativePanTiltTranslationSpace or []):
            if "TranslationSpaceFov" in (s.URI or ""):
                fov = s
                break
        out["fov"] = fov
        st = await ptz.GetStatus({"ProfileToken": prof.token})
        out["status"] = st
        presets = await ptz.GetPresets({"ProfileToken": prof.token})
        out["presets"] = {(p.Name or f"preset {p.token}").lower(): p.token for p in presets or []}
        f = out["features"]
        if c.DefaultContinuousPanTiltVelocitySpace:
            f.append("pt")
        if c.DefaultContinuousZoomVelocitySpace:
            f.append("zoom")
        if c.DefaultRelativePanTiltTranslationSpace:
            f.append("pt-r")
        if c.DefaultRelativeZoomTranslationSpace:
            f.append("zoom-r")
        if c.DefaultAbsoluteZoomPositionSpace:
            f.append("zoom-a")
        if fov is not None and c.DefaultRelativePanTiltTranslationSpace is not None:
            f.append("pt-r-fov")
        if out["imaging"] and out["vs"]:
            try:
                img = await cam.create_imaging_service()
                s = await img.GetImagingSettings({"VideoSourceToken": out["vs"]})
                if s.Focus:
                    f.append("focus")
            except Exception as e:  # noqa: BLE001
                out["log"].append(f"DEBUG Focus not supported: {e}")
        try:
            caps = await ptz.GetServiceCapabilities()
            ms = getattr(caps, "MoveStatus", None)
            if ms is None and getattr(caps, "_attr_1", None):
                ms = caps._attr_1.get("MoveStatus")
            out["movestatus_raw"] = ms
        except Exception as e:  # noqa: BLE001
            out["movestatus_raw"] = None
            out["log"].append(f"does not support the ONVIF GetServiceCapabilities method: {e}")
        return out
    finally:
        await cam.close()


@test("X-FRIGATE-PTZINFO", "Frigate 0.17.2 init: profile choice and the PTZ features it shows", "clients",
      needs=("svc.ptz",), clients=("frigate",), ref="frigate/ptz/onvif.py _init_onvif (v0.17.2)")
def t_frigate_info(r):
    _need_lib(r)
    o = asyncio.run(_frigate_init(r))
    if "fatal" in o:
        r.fail(o["fatal"])
    r.d["frigate"] = o
    r.info(f"profile {o['profile']}; features {o['features']} (pt-r-fov only shows in Frigate with "
           "autotracking enabled)")
    for line in o["log"]:
        r.info(line[:200])
    r.check("pt" in o["features"], "no 'pt': Frigate shows no pan/tilt arrows")
    r.check("zoom" in o["features"] or not r.f.get("ptz.cont.zoom"),
            "the camera has continuous zoom but Frigate's 'zoom' flag is off")
    r.check("focus" in o["features"] or not r.f.get("imaging.focus"),
            "the camera has focus moves but Frigate's 'focus' flag is off", else_warn=True)
    r.check(o["imaging"] or not r.f.get("svc.imaging"),
            "Imaging offered but invisible to Frigate (GetCapabilities order); no focus buttons", else_warn=True)


@test("X-FRIGATE-AUTOTRACK", "Frigate 0.17.2 autotracking prerequisites", "clients", needs=("svc.ptz",),
      clients=("frigate",), ref="frigate/ptz/autotrack.py _autotracker_setup; docs §Frigate checklist")
def t_frigate_at(r):
    _need_lib(r)
    o = r.d.get("frigate") or asyncio.run(_frigate_init(r))
    if "fatal" in o:
        r.fail("Disabling autotracking: Unable to initialize onvif (" + o["fatal"] + ")")
    if "pt-r-fov" not in o["features"]:
        r.fail("Disabling autotracking: FOV relative movement not supported")
    fov = o["fov"]
    rng = [fov.XRange.Min, fov.XRange.Max, fov.YRange.Min, fov.YRange.Max]
    r.check(all(v is not None and math.isfinite(float(v)) for v in rng),
            f"FOV space ranges {rng}: Frigate interpolates onto them, ±INF gives NaN moves (advertise -1..1)")
    ms = o.get("movestatus_raw")
    ok = ms is True or (isinstance(ms, str) and ms.lower() == "true")
    r.check(ok, f"Disabling autotracking: ONVIF MoveStatus not supported (GetServiceCapabilities MoveStatus "
                f"reads {ms!r}; it must be the unprefixed literal \"true\")")
    st = o["status"]
    pos = getattr(st, "Position", None)
    r.check(pos is not None and pos.PanTilt is not None,
            "GetStatus Position/PanTilt reads None: Frigate's RelativeMove template fails at init")
    mv = getattr(st, "MoveStatus", None)
    pt = getattr(mv, "PanTilt", None) if mv is not None else None
    r.check(pt in ("IDLE", "MOVING") or mv in ("IDLE", "MOVING"),
            "Camera does not support the ONVIF GetStatus method (MoveStatus.PanTilt neither IDLE nor MOVING)")
    want = (getattr(r.ctx.args, "return_preset", None) or "home").lower()
    r.check(want in o["presets"], f"'{want}' is not a valid preset (Frigate's return_preset; presets: "
                                  f"{sorted(o['presets'])[:12]})")
    # zooming
    opts = o["opts"]
    absz = opts.Spaces.AbsoluteZoomPositionSpace or []
    relz = [s for s in (opts.Spaces.RelativeZoomTranslationSpace or []) if TGEN_ZOOM == s.URI]
    if pos is None or pos.Zoom is None:
        r.warn("Disabling autotracking zooming: Relative zoom not supported (GetStatus has no Position.Zoom)")
    if "zoom-a" in o["features"]:
        r.check(absz, "Disabling autotracking zooming: Absolute zoom not supported (no AbsoluteZoomPositionSpace)",
                else_warn=True)
        if absz:
            r.info(f"absolute zoom XRange {absz[0].XRange.Min}..{absz[0].XRange.Max}"
                   f"{'' if (absz[0].XRange.Min, absz[0].XRange.Max) == (0, 1) else ' (Frigate maps raw Min/Max: exact only for 0..1)'}")
    r.info(f"zooming modes possible: absolute={'zoom-a' in o['features'] and bool(absz)}, "
           f"relative={'zoom-r' in o['features'] and bool(relz)}")


@test("X-FRIGATE-POLL", "GetStatus answers fast (Frigate polls it in a tight loop)", "clients",
      needs=("ptz",), clients=("frigate",), ref="frigate/ptz/onvif.py get_camera_status")
def t_frigate_poll(r):
    tok = r.d["ptz_profile"]
    times = []
    for _ in range(20):
        rep = r.call("ptz", "GetStatus", f"<ProfileToken>{tok}</ProfileToken>")
        if not rep.ok:
            r.fail(f"GetStatus: {rep.why()}")
        times.append(rep.elapsed * 1000)
    med, worst = statistics.median(times), max(times)
    r.info(f"20 polls: median {med:.0f} ms, worst {worst:.0f} ms")
    r.check(med < 250, f"median GetStatus {med:.0f} ms: Frigate's move timing includes one poll period",
            else_warn=True)


@test("X-FRIGATE-STRAYZOOM", "RelativeMove with Frigate 0.17.2's stray Zoom does not zoom", "clients",
      cat=MOVE, needs=("ptz", "ptz.rel.pt.fov"), clients=("frigate",),
      ref="Frigate 0.17.2 absolute zoom mode: every RelativeMove carries Zoom = zoom at init")
def t_strayzoom(r):
    from .t_ptz import status, wait_idle
    tok = r.d["ptz_profile"]
    z_orig = (status(r) or {}).get("z")
    if z_orig is None:
        r.na("GetStatus reports no zoom position")

    def absz(z):
        r.call("ptz", "AbsoluteMove", f"<ProfileToken>{tok}</ProfileToken><Position>"
                                      f'<tt:Zoom x="{z:.3f}"/></Position><Speed><tt:Zoom x="1"/></Speed>')
        wait_idle(r, 20)
        time.sleep(0.5)
        return (status(r) or {}).get("z")
    # the risky case is Frigate starting while zoomed in: get there first
    z0 = z_orig
    if z_orig < 0.05 and r.f.get("ptz.abs.zoom"):
        z0 = absz(0.2)
        r.info(f"zoomed to {z0} first (Frigate started while zoomed in)")
    if z0 is None or z0 < 0.05:
        r.warn(f"zoom at {z0}: a stray Zoom of ~0 proves little")
    try:
        for x in (0.1, -0.1):
            rep = r.call("ptz", "RelativeMove", f"<ProfileToken>{tok}</ProfileToken><Translation>"
                         f'<tt:PanTilt x="{x}" y="0" space="{FOV_SPACE}"/><tt:Zoom x="{z0}" space="{TGEN_ZOOM}"/>'
                         '</Translation><Speed><tt:PanTilt x="1" y="1"/></Speed>')
            r.check(rep.ok, f"RelativeMove pan {x:+} with Zoom {z0}: {rep.why()}")
            wait_idle(r, 15)
            time.sleep(1.0)
            z = (status(r) or {}).get("z")
            r.check(z is not None and abs(z - z0) < 0.03,
                    f"zoom moved {z0} -> {z} on a pan move carrying Frigate's stray Zoom x={z0}: "
                    "every tracking move would zoom")
            r.info(f"pan {x:+} FOV with Zoom x={z0}: zoom now {z}")
    finally:
        if z0 != z_orig and r.f.get("ptz.abs.zoom"):
            r.info(f"zoom restored to {absz(z_orig)}")


# ------------------------------------------------------------------ auth forms
@test("X-AUTH-FORMATS", "Each client's UsernameToken form is accepted", "clients",
      clients=("frigate", "ha", "go2rtc"),
      ref="Frigate 0.17.2 Created '+00:00' whole seconds; HA/Frigate dev 'Z'; go2rtc RFC3339Nano, ASCII nonce")
def t_auth_forms(r):
    import base64
    import datetime as dt
    import hashlib
    import secrets
    import string
    now = dt.datetime.now(dt.timezone.utc) + dt.timedelta(seconds=r.c.time_offset)
    forms = {
        "Frigate 0.17.2 (+00:00)": now.replace(microsecond=0).isoformat(),
        "HA / Frigate dev (Z, ms)": now.strftime("%Y-%m-%dT%H:%M:%S.") + f"{now.microsecond // 1000:03d}Z",
        "go2rtc (Z, 9 digits)": now.strftime("%Y-%m-%dT%H:%M:%S.") + f"{now.microsecond:06d}123Z",
    }
    for name, created in forms.items():
        hdr = r.c.security_header(created=created)
        if name.startswith("go2rtc"):
            raw = "".join(secrets.choice(string.ascii_letters) for _ in range(16)).encode()
            dig = base64.b64encode(hashlib.sha1(raw + created.encode() + r.c.password.encode()).digest()).decode()
            hdr = re.sub(r"(<wsse:Nonce[^>]*>)[^<]*", lambda m: m.group(1) + base64.b64encode(raw).decode(), hdr)
            hdr = re.sub(r"(<wsse:Password[^>]*>)[^<]*", lambda m: m.group(1) + dig, hdr)
        rep = r.call("device", "GetDeviceInformation", header=hdr)
        r.check(rep.ok, f"{name}: Created={created} refused: {rep.why()}")


# ------------------------------------------------------------------ go2rtc
@test("X-GO2RTC-SNAPSHOT", "go2rtc's GetSnapshotUri, posted to the Imaging address, works", "clients",
      needs=("svc.media", "svc.imaging"), clients=("go2rtc",),
      ref="go2rtc v1.9.10 pkg/onvif: GetSnapshotUri sent to the Imaging XAddr")
def t_go2rtc(r):
    p = r.d["profiles"][0]["token"]
    rep = r.call("media", "GetSnapshotUri", f"<ProfileToken>{p}</ProfileToken>", url=r.c.url("imaging"))
    # go2rtc reads replies with regexes, so judge it the same way
    uri = re.search(r"<(?:\w+:)?Uri>([^<]+)<", rep.text or "")
    r.check(rep.status == 200 and uri, f"trt:GetSnapshotUri at the Imaging address: HTTP {rep.status}, "
                                       "no Uri (go2rtc's onvif:// &snapshot fails)", else_warn=True)
    if uri and not rep.ok:
        r.warn(f"the reply carries a Uri go2rtc's regex finds, but is not valid SOAP ({rep.why()[:120]})")
    caps = r.call("media", "GetServiceCapabilities")
    r.check('SnapshotUri="true"' in caps.text, "Media capabilities lack the literal SnapshotUri=\"true\" "
                                               "go2rtc's /api/onvif greps for", else_warn=True)
    prof = r.call("media", "GetProfiles")
    toks = re.findall(r'Profiles.+?token="([^"]+)"', prof.text)
    r.info(f"go2rtc's regex finds profile tokens {toks[:4]}")


# ------------------------------------------------------------------ Home Assistant
@test("X-HA-SETUP", "Home Assistant setup: MAC, H264 profiles, snapshot, clock", "clients",
      needs=("svc.media",), clients=("ha",), ref="homeassistant/components/onvif/device.py (2026.11)")
def t_ha_setup(r):
    rep = r.ok("device", "GetNetworkInterfaces")
    en = [i for i in rep.x("tds:NetworkInterfaces") if (i.findtext(f"{{{NS['tt']}}}Enabled") or "") == "true"]
    mac = en[-1].findtext(f"{{{NS['tt']}}}Info/{{{NS['tt']}}}HwAddress") if en else None
    r.check(mac or r.d.get("info", {}).get("SerialNumber"),
            "no MAC on an enabled interface and no serial: HA aborts with no_mac")
    h264 = [p for p in r.d["profiles"] if p["encoding"] == "H264"]
    r.check(h264, "no H264 profile: HA aborts with no_h264")
    r.info(f"unique id from MAC {mac}; camera entities: {[p['token'] for p in h264]}")
    r.check(r.f.get("snapshot"), "Media SnapshotUri capability false: HA falls back to ffmpeg stills",
            else_warn=True)
    off = abs(r.d.get("time_offset", 0))
    r.check(off < 5, f"clock {off:.0f} s off: HA sets the camera clock if Manual, else warns", else_warn=True)


@test("X-HA-EVENTS", "Home Assistant events: lifetime, literal tns1: topics, Data values", "clients",
      cat="session", needs=("svc.events",), clients=("ha",),
      ref="homeassistant/components/onvif/event.py; onvif_parsers 2.5.0")
def t_ha_events(r):
    from .t_events import _msgs, _pull, _sub_call
    rep = r.call("events", "CreatePullPointSubscription", "<InitialTerminationTime>PT600S</InitialTerminationTime>")
    if not rep.ok:
        r.fail(f"CreatePullPointSubscription: {rep.why()}")
    addr = rep.t("tev:SubscriptionReference/wsa:Address")
    try:
        import datetime as dt

        def t(s):
            return dt.datetime.fromisoformat(s.replace("Z", "+00:00")) if s else None
        cur, term = t(rep.t("wsnt:CurrentTime")), t(rep.t("wsnt:TerminationTime"))
        if cur and term:
            life = (term - cur).total_seconds()
            r.check(life >= 300, f"asked PT600S, granted {life:.0f} s: HA flags broken relative times and "
                                 "switches to absolute Renew", else_warn=True)
            r.info(f"subscription lifetime {life:.0f} s")
        sp = _sub_call(r, addr, "tev", "SetSynchronizationPoint")
        pull = _pull(r, addr, "PT2S", 100)
        raw_topics = re.findall(r"<(?:\w+:)?Topic[^>]*>([^<]*)<", pull.text)
        for tp in sorted(set(raw_topics)):
            r.check(tp.strip().startswith("tns1:"), f"topic '{tp}' does not use the literal tns1: prefix "
                                                    "(HA looks topics up as text)")
        for topic, op, data in _msgs(pull):
            r.check(data, f"{topic}: no Data/SimpleItem (HA reads Data.SimpleItem[0].Value)", else_warn=True)
        r.info(f"topics HA would see: {sorted(set(raw_topics))}; SetSynchronizationPoint {'ok' if sp.ok else sp.why()}")
    finally:
        _sub_call(r, addr, "wsnt", "Unsubscribe")
