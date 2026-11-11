"""Device management, security (auth) and WS-Discovery tests."""
from __future__ import annotations

import datetime as dt
import uuid
from urllib.parse import urlsplit

from . import net
from .core import READ, test
from .soap import NS, xp, xt

ALL = ("S", "T", "M", "G")


# ------------------------------------------------------------------ auth
@test("DEVICE-3-1-1", "GetSystemDateAndTime answers without credentials", "device",
      clients=("frigate", "ha"), profiles=ALL, ref="Core 5.9.4.3 pre-auth; Base test spec")
def t_time(r):
    rep = r.call("device", "GetSystemDateAndTime", auth="none")
    if not rep.ok:
        r.fail(f"unauthenticated GetSystemDateAndTime: {rep.why()} (clients read the clock before auth)")
    r.check(rep.x(".//tt:UTCDateTime"), "no UTCDateTime")
    tz = rep.t(".//tt:TimeZone/tt:TZ")
    r.info(f"type {rep.t('.//tt:DateTimeType')}, TZ {tz}, offset from this PC {r.d.get('time_offset', 0):+.1f} s")
    off = abs(r.d.get("time_offset", 0))
    r.check(off < 5, f"clock off by {off:.0f} s: WS-UsernameToken digests may be refused by strict "
                     "devices; Frigate/HA correct for it, others may not", else_warn=True)


@test("SECURITY-1-1-1", "WS-UsernameToken digest is accepted", "device",
      clients=("frigate", "ha", "go2rtc"), profiles=ALL, ref="Core 5.12.2")
def t_wsse(r):
    rep = r.call("device", "GetDeviceInformation", auth="wsse")
    if not rep.ok:
        r.fail(f"GetDeviceInformation with a UsernameToken digest: {rep.why()}")


@test("SECURITY-1-1-2", "HTTP digest is accepted", "device", profiles=("T", "M"),
      ref="Core 5.12.1 (HTTP digest mandatory since 2.5)")
def t_digest(r):
    rep = r.call("device", "GetDeviceInformation", auth="digest")
    if not rep.ok:
        r.fail(f"GetDeviceInformation with HTTP digest only: {rep.why()}")


@test("X-AUTH-1", "Protected operations refuse anonymous callers", "device", profiles=ALL,
      ref="Core 5.9.4 access classes")
def t_anon(r):
    for svc, op, inner in (("device", "GetDeviceInformation", ""), ("media", "GetProfiles", ""),
                           ("device", "GetUsers", "")):
        if svc != "device" and not r.f.get(f"svc.{svc}"):
            continue
        rep = r.call(svc, op, inner, auth="none")
        if rep.ok:
            r.check(False, f"{op} answered without credentials")
        else:
            ok = rep.status == 401 or (rep.fault and rep.fault.has("NotAuthorized", "FailedAuthentication",
                                                                      "Sender"))
            r.check(ok, f"{op}: refused, but not as NotAuthorized/401 ({rep.why()})", else_warn=True)
            r.info(f"{op} anonymous -> {rep.why()}")
    if r.f.get("svc.events"):
        rep = r.call("events", "CreatePullPointSubscription",
                     "<InitialTerminationTime>PT10S</InitialTerminationTime>", auth="none")
        if rep.ok:
            r.check(False, "CreatePullPointSubscription answered without credentials "
                           "(anyone can read the camera's events)")
            addr = rep.t("tev:SubscriptionReference/wsa:Address")
            if addr:
                r.call(NS["wsnt"], "Unsubscribe", url=addr)
        else:
            r.info(f"CreatePullPointSubscription anonymous -> {rep.why()}")


@test("X-AUTH-2", "A wrong password is refused", "device", profiles=ALL)
def t_badpw(r):
    hdr = r.c.security_header(password=r.c.password + "x")
    rep = r.call("device", "GetDeviceInformation", header=hdr)
    r.check(not rep.ok, "GetDeviceInformation accepted a wrong password digest")
    r.info(f"wrong password -> {rep.why()}")


@test("X-AUTH-3", "A replayed (1 h old) UsernameToken is refused", "device",
      ref="WSS UsernameToken Profile 1.0 §4 (Created/Nonce freshness)")
def t_stale(r):
    old = (dt.datetime.now(dt.timezone.utc) + dt.timedelta(seconds=r.c.time_offset - 3600))
    hdr = r.c.security_header(created=old.strftime("%Y-%m-%dT%H:%M:%SZ"))
    rep = r.call("device", "GetDeviceInformation", header=hdr)
    r.check(not rep.ok, "a digest with Created one hour old was accepted (replayable)", else_warn=True)
    r.info(f"stale token -> {rep.why()}")


# ------------------------------------------------------------------ device
@test("DEVICE-3-1-9", "GetDeviceInformation", "device", clients=("frigate", "ha"), profiles=ALL)
def t_info(r):
    rep = r.ok("device", "GetDeviceInformation")
    got = {e.tag.rsplit("}", 1)[-1]: (e.text or "").strip() for e in rep.body}
    for k in ("Manufacturer", "Model", "FirmwareVersion", "SerialNumber", "HardwareId"):
        r.check(k in got, f"{k} missing")
    r.check(got.get("SerialNumber"), "SerialNumber is empty (HA keys the device on it, or the MAC)",
            else_warn=True)
    r.check(got.get("SerialNumber") not in ("SN1234567890", "0", "000000"),
            f"SerialNumber {got.get('SerialNumber')} looks like a placeholder (every unit the same?)",
            else_warn=True)
    r.info(", ".join(f"{k}={v}" for k, v in got.items()))


@test("DEVICE-1-1-13", "GetServices lists the device service", "device",
      clients=("ha",), profiles=ALL)
def t_services(r):
    rep = r.ok("device", "GetServices", "<IncludeCapability>false</IncludeCapability>")
    nss = rep.x("tds:Service/tds:Namespace/text()")
    r.check(NS["tds"] in nss, "the device service is not listed")
    for s in rep.x("tds:Service"):
        r.info(f'{xt(s, "tds:Namespace").rsplit("/", 2)[-2]} {xt(s, "tds:Version/tt:Major")}.'
               f'{xt(s, "tds:Version/tt:Minor")} at {urlsplit(xt(s, "tds:XAddr", "")).path}')


@test("DEVICE-1-1-31", "Every advertised XAddr is reachable and answers", "device", profiles=ALL)
def t_xaddr(r):
    for ns, s in r.d.get("services", {}).items():
        u = urlsplit(s["xaddr"])
        r.check(u.hostname in (r.ctx.host,) or u.hostname is None,
                f"{s['key'] or ns} XAddr advertises host {u.hostname}, reached at {r.ctx.host}", else_warn=True)
        if not s["key"] or s["key"] == "device":
            continue
        rep = r.call(s["key"], "GetServiceCapabilities")
        r.check(rep.ok, f"{s['key']} GetServiceCapabilities at {u.path}: {rep.why()}")


@test("DEVICE-1-1-2", "GetCapabilities (All)", "device", clients=("frigate", "ha"),
      profiles=("S", "T"), ref="Core 8.1.2.2 (deprecated, still used by clients)")
def t_caps(r):
    rep = r.ok("device", "GetCapabilities", "<Category>All</Category>")
    caps = rep.x("tds:Capabilities/*")
    r.info("categories: " + ", ".join(c.tag.rsplit("}", 1)[-1] for c in caps))
    r.check(rep.x("tds:Capabilities/tt:Device/tt:XAddr"), "no Device XAddr")


@test("DEVICE-1-1-30", "GetServices and GetCapabilities agree", "device", profiles=("S", "T"))
def t_consistency(r):
    rep = r.ok("device", "GetCapabilities", "<Category>All</Category>")
    svc = {s["key"]: s["xaddr"] for s in r.d.get("services", {}).values() if s["key"]}
    for key, tag in (("media", "Media"), ("ptz", "PTZ"), ("imaging", "Imaging"), ("events", "Events")):
        a = rep.t(f"tds:Capabilities/tt:{tag}/tt:XAddr")
        if a or key in svc:
            r.check(a and key in svc and urlsplit(a).path == urlsplit(svc[key]).path,
                    f"{tag}: GetCapabilities {a} vs GetServices {svc.get(key)}")


@test("DEVICE-1-1-18", "Device GetServiceCapabilities", "device", profiles=ALL)
def t_devcaps(r):
    rep = r.ok("device", "GetServiceCapabilities")
    for k in ("Network", "Security", "System"):
        el = rep.x(f"tds:Capabilities/tds:{k}")
        r.check(el, f"{k} capabilities missing")
    sec = rep.x("tds:Capabilities/tds:Security")
    if sec:
        a = sec[0].attrib
        r.info("security: UsernameToken=%s HttpDigest=%s TLS1.2=%s" % (
            a.get("UsernameToken"), a.get("HttpDigest"), a.get("TLS1.2")))


@test("DEVICE-2-1-17", "GetNetworkInterfaces (MAC)", "device", clients=("ha",), profiles=ALL)
def t_netif(r):
    rep = r.ok("device", "GetNetworkInterfaces")
    macs = rep.x(".//tt:HwAddress/text()")
    r.check(macs, "no HwAddress")
    r.info("MAC " + ", ".join(macs))
    if r.ctx.expect_mac:
        r.check(r.ctx.mac_ok, f"expected a MAC ending {r.ctx.expect_mac}")


@test("X-DEV-SCOPES", "GetScopes: profile claims match the services", "device", profiles=ALL,
      ref="Core 7.3.2.2 scopes")
def t_scopes(r):
    rep = r.ok("device", "GetScopes")
    scopes = rep.x(".//tt:ScopeItem/text()")
    r.info(" ".join(s.replace("onvif://www.onvif.org/", "") for s in scopes))
    claims = [s.rsplit("/", 1)[-1] for s in scopes if "/Profile/" in s]
    if "T" in claims:
        r.check(r.f.get("svc.media2"), "claims Profile T without a Media2 service (T requires Media2)")
    if "G" in claims:
        r.check(False, "claims Profile G without recording/search/replay services")
    r.check(any("/type/" in s for s in scopes), "no onvif://www.onvif.org/type/ scope", else_warn=True)
    r.check(any("/name/" in s for s in scopes), "no name scope", else_warn=True)


@test("DEVICE-4-1-1", "GetUsers", "device", profiles=ALL)
def t_users(r):
    rep = r.ok("device", "GetUsers")
    users = [(xt(u, "tt:Username"), xt(u, "tt:UserLevel")) for u in rep.x("tds:User")]
    r.check(users, "no users listed")
    r.info(", ".join(f"{u} ({lvl})" for u, lvl in users))


@test("DEVICE-2-1-33", "GetNetworkProtocols (RTSP port)", "device", profiles=("S", "T"))
def t_protocols(r):
    rep = r.ok("device", "GetNetworkProtocols")
    got = {xt(p, "tt:Name"): (xt(p, "tt:Enabled"), p.xpath("tt:Port/text()", namespaces=NS))
           for p in rep.x("tds:NetworkProtocols")}
    r.info(", ".join(f"{k} {'on' if v[0] == 'true' else 'off'} {'/'.join(v[1])}" for k, v in got.items()))
    r.check("RTSP" in got, "RTSP not listed", else_warn=True)


@test("X-DEV-READS", "Other device reads answer (hostname, NTP, DNS, discovery mode, WSDL URL)",
      "device", profiles=ALL)
def t_misc(r):
    for op in ("GetHostname", "GetNTP", "GetDNS", "GetDiscoveryMode", "GetWsdlUrl",
               "GetNetworkDefaultGateway", "GetSystemUris", "GetEndpointReference"):
        rep = r.call("device", op)
        if rep.ok:
            r.info(f"{op} ok")
        elif rep.fault and rep.fault.has("ActionNotSupported"):
            r.info(f"{op}: ActionNotSupported")
        else:
            r.check(False, f"{op}: {rep.why()}", else_warn=True)


@test("DEVICE-1-1-9", "An unknown operation gets a SOAP fault", "device", profiles=ALL,
      ref="Core 5.11.2 (ActionNotSupported)")
def t_unknown(r):
    rep = r.call("device", "GetFooBarNotAnOperation")
    r.expect_fault(rep, "ActionNotSupported", "NotSupported")


@test("DEVICE-6-1-3", "Non-standard namespace prefixes are understood", "device", profiles=ALL,
      ref="Base test spec DEVICE-6-1-3")
def t_prefixes(r):
    env = (f'<?xml version="1.0" encoding="UTF-8"?><zz:Envelope xmlns:zz="{NS["s"]}">'
           f'<zz:Header>{r.c.security_header().replace("s:mustUnderstand", "zz:mustUnderstand")}</zz:Header>'
           f'<zz:Body><qq:GetDeviceInformation xmlns:qq="{NS["tds"]}"/></zz:Body></zz:Envelope>')
    rep = r.call("device", "GetDeviceInformation", raw=env)
    r.check(rep.ok and rep.x("tds:Manufacturer"), f"prefixes zz:/qq: refused: {rep.why()}")


@test("DEVICE-6-1-1", "Default namespaces on each element are understood", "device", profiles=ALL,
      ref="Base test spec DEVICE-6-1-1")
def t_defaultns(r):
    env = (f'<?xml version="1.0" encoding="UTF-8"?><Envelope xmlns="{NS["s"]}">'
           f'<Header>{r.c.security_header().replace("s:mustUnderstand", "mustUnderstand")}</Header>'
           f'<Body><GetDeviceInformation xmlns="{NS["tds"]}"/></Body></Envelope>')
    rep = r.call("device", "GetDeviceInformation", raw=env)
    r.check(rep.ok and rep.x("tds:Manufacturer"), f"default-namespace request refused: {rep.why()}")


# ------------------------------------------------------------------ discovery
@test("DISCOVERY-1-1-6", "Unicast WS-Discovery Probe gets a ProbeMatch", "discovery",
      clients=("ha", "frigate"), profiles=ALL, ref="Core 7.3")
def t_probe(r):
    m = [x for x in net.probe(r.ctx.host, timeout=3) if x.epr or x.xaddrs]
    if not m:
        r.fail("no ProbeMatch on UDP 3702 (HA's discovery and ODM will not see the camera)")
    pm = m[0]
    r.info(f"EPR {pm.epr}; Types {' '.join(pm.types)}; XAddrs {' '.join(pm.xaddrs)}")
    r.check(any(t.endswith(":NetworkVideoTransmitter") for t in pm.types),
            "Types lacks dn:NetworkVideoTransmitter")
    r.check(any(r.ctx.host in x for x in pm.xaddrs), "no XAddr with the camera's address", else_warn=True)
    r.check(pm.epr.startswith("urn:uuid:"), "EPR is not urn:uuid:", else_warn=True)
    r.d["probe"] = pm


@test("DISCOVERY-1-1-3", "Probe filtered by scope matches", "discovery", profiles=ALL)
def t_probe_scope(r):
    msg = net.probe_message(types="", scopes="onvif://www.onvif.org/type/video_encoder")
    hit = [x for x in net.probe(r.ctx.host, timeout=2, message=msg) if x.epr or x.xaddrs]
    has = any("type/video_encoder" in s for s in r.d.get("scopes", []))
    if has:
        r.check(hit, "scope onvif://www.onvif.org/type/video_encoder is set but a probe on it got no match")
    else:
        r.info("device has no type/video_encoder scope; probing on it" + (" matched anyway" if hit else " got nothing"))
    msg = net.probe_message(types="", scopes=f"onvif://www.onvif.org/name/{uuid.uuid4().hex}")
    miss = [x for x in net.probe(r.ctx.host, timeout=2, message=msg) if x.epr]
    r.check(not miss, "a probe on a scope the device lacks still matched", else_warn=True)


@test("DISCOVERY-1-1-5", "An invalid probe is ignored or faulted, not crashed on", "discovery",
      profiles=ALL)
def t_probe_bad(r):
    msg = net.probe_message(types="dn:NetworkVideoTransmitter").replace("<d:Probe>", "<d:Probe><d:Bogus>").replace(
        "</d:Probe>", "</d:Bogus></d:Probe>")
    net.probe(r.ctx.host, timeout=1.5, message=msg)
    again = [x for x in net.probe(r.ctx.host, timeout=3) if x.epr]
    r.check(again, "no ProbeMatch after an invalid probe (did the WS-Discovery daemon die?)")
