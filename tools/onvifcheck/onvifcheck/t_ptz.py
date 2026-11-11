"""PTZ tests. Reads first; motion tests (cat MOVE) need --allow-move and a MAC
match, and leave the head where it started (matched moves, or an absolute
return when the camera reports its position)."""
from __future__ import annotations

import time

from .core import FOV_SPACE, MOVE, PRESET, SPACES, test
from .soap import xp, xt

PT = ("S", "T")   # PTZ is "conditional: if supported" in S and T
GEN = {
    "AbsolutePanTiltPositionSpace": (SPACES + "PanTiltSpaces/PositionGenericSpace", (-1, 1), (-1, 1)),
    "AbsoluteZoomPositionSpace": (SPACES + "ZoomSpaces/PositionGenericSpace", (0, 1), None),
    "RelativePanTiltTranslationSpace": (SPACES + "PanTiltSpaces/TranslationGenericSpace", (-1, 1), (-1, 1)),
    "RelativeZoomTranslationSpace": (SPACES + "ZoomSpaces/TranslationGenericSpace", (-1, 1), None),
    "ContinuousPanTiltVelocitySpace": (SPACES + "PanTiltSpaces/VelocityGenericSpace", (-1, 1), (-1, 1)),
    "ContinuousZoomVelocitySpace": (SPACES + "ZoomSpaces/VelocityGenericSpace", (-1, 1), None),
    "PanTiltSpeedSpace": (SPACES + "PanTiltSpaces/GenericSpeedSpace", (0, 1), None),
    "ZoomSpeedSpace": (SPACES + "ZoomSpaces/ZoomGenericSpeedSpace", (0, 1), None),
}
# the order PTZConfiguration's children must come in (tt:PTZConfiguration)
CFG_ORDER = ["Name", "UseCount", "MoveRamp", "PresetRamp", "PresetTourRamp", "NodeToken",
             "DefaultAbsolutePantTiltPositionSpace", "DefaultAbsoluteZoomPositionSpace",
             "DefaultRelativePanTiltTranslationSpace", "DefaultRelativeZoomTranslationSpace",
             "DefaultContinuousPanTiltVelocitySpace", "DefaultContinuousZoomVelocitySpace",
             "DefaultPTZSpeed", "DefaultPTZTimeout", "PanTiltLimits", "ZoomLimits", "Extension"]


def P(r):
    return r.d["ptz_profile"]


def node(r):
    return r.d["ptz_nodes"][0]


# ------------------------------------------------------------------ reads
@test("PTZ-8-1-1", "PTZ GetServiceCapabilities", "ptz", needs=("svc.ptz",), clients=("frigate",),
      profiles=PT)
def t_caps(r):
    rep = r.ok("ptz", "GetServiceCapabilities")
    cap = rep.x("tptz:Capabilities")
    r.check(cap, "no Capabilities element")
    if cap:
        r.info(" ".join(f"{k}={v}" for k, v in cap[0].attrib.items()) or "no attributes")


@test("PTZ-1-1-1", "GetNodes: spaces, preset count, home support", "ptz", needs=("svc.ptz",),
      clients=("frigate", "ha"), profiles=PT)
def t_nodes(r):
    rep = r.ok("ptz", "GetNodes")
    nodes = rep.x("tptz:PTZNode")
    if not nodes:
        r.fail("no PTZNode")
    for n in nodes:
        r.check(xp(n, "tt:SupportedPTZSpaces"), f"{n.get('token')}: no SupportedPTZSpaces")
        r.check(xt(n, "tt:MaximumNumberOfPresets") is not None, f"{n.get('token')}: no MaximumNumberOfPresets")
        r.check(xt(n, "tt:HomeSupported") is not None, f"{n.get('token')}: no HomeSupported")
    for n in r.d["ptz_nodes"]:
        sp = ", ".join(f"{k.replace('Space', '')}: " + "/".join(s["uri"].rsplit("/", 1)[-1] for s in v)
                       for k, v in n["spaces"].items() if v)
        r.info(f"{n['token']}: presets {n['max_presets']}, home {n['home']} fixed {n['fixed_home']}, "
               f"aux {n['aux'] or '-'}; {sp}")


@test("PTZ-1-1-2", "GetNode", "ptz", needs=("ptz",), profiles=PT)
def t_node(r):
    rep = r.ok("ptz", "GetNode", f"<NodeToken>{node(r)['token']}</NodeToken>")
    r.check(rep.x("tptz:PTZNode"), "no PTZNode")


@test("PTZ-1-1-4", "GetNode with an invalid token faults", "ptz", needs=("ptz",), profiles=PT)
def t_node_bad(r):
    r.expect_fault(r.call("ptz", "GetNode", "<NodeToken>no_such_node_xyz</NodeToken>"), "NoEntity", "InvalidArgVal")


@test("PTZ-2-1-1", "GetConfigurations", "ptz", needs=("svc.ptz",), clients=("frigate",), profiles=PT)
def t_cfgs(r):
    rep = r.ok("ptz", "GetConfigurations")
    r.check(rep.x("tptz:PTZConfiguration"), "no PTZConfiguration")
    for c in r.d["ptz_cfgs"]:
        r.info(f"{c['token']} node {c['node']}: " + ", ".join(
            f"{k.replace('Default', '')}={v.rsplit('/', 1)[-1]}" for k, v in c["defaults"].items()))


@test("PTZ-2-1-2", "GetConfiguration", "ptz", needs=("ptz",), profiles=PT)
def t_cfg(r):
    tok = r.d["ptz_cfgs"][0]["token"] if r.d.get("ptz_cfgs") else r.na("no configuration")
    rep = r.ok("ptz", "GetConfiguration", f"<PTZConfigurationToken>{tok}</PTZConfigurationToken>")
    r.check(rep.x("tptz:PTZConfiguration"), "no PTZConfiguration")


@test("PTZ-2-1-3", "GetConfigurationOptions", "ptz", needs=("ptz",), clients=("frigate",), profiles=PT)
def t_cfgopts(r):
    tok = r.d["ptz_cfgs"][0]["token"]
    rep = r.ok("ptz", "GetConfigurationOptions", f"<ConfigurationToken>{tok}</ConfigurationToken>")
    o = rep.x("tptz:PTZConfigurationOptions")
    r.check(o and xp(o[0], "tt:Spaces"), "no Spaces in the options")
    to = rep.t("tptz:PTZConfigurationOptions/tt:PTZTimeout/tt:Min"), rep.t("tptz:PTZConfigurationOptions/tt:PTZTimeout/tt:Max")
    r.info(f"timeout {to[0]}..{to[1]}; spaces " + ", ".join(sorted({u.rsplit('/', 1)[-1] for u in rep.x('.//tt:URI/text()')})))
    r.d["ptz_opts"] = rep.body


@test("PTZ-2-1-6", "Configuration defaults are spaces the node supports", "ptz", needs=("ptz",), profiles=PT)
def t_cfg_node(r):
    n = {x["token"]: x for x in r.d["ptz_nodes"]}
    for c in r.d["ptz_cfgs"]:
        nd = n.get(c["node"])
        if not r.check(nd, f"{c['token']}: NodeToken {c['node']} is not a node"):
            continue
        uris = {s["uri"] for v in nd["spaces"].values() for s in v}
        for k, v in c["defaults"].items():
            if v.startswith("http"):
                r.check(v in uris, f"{c['token']}: {k} {v.rsplit('/', 1)[-1]} not in the node's spaces")


@test("PTZ-2-1-7", "Configuration defaults appear in the configuration options", "ptz", needs=("ptz",),
      profiles=PT)
def t_cfg_opts(r):
    c = r.d["ptz_cfgs"][0]
    rep = r.ok("ptz", "GetConfigurationOptions", f"<ConfigurationToken>{c['token']}</ConfigurationToken>")
    uris = set(rep.x(".//tt:URI/text()"))
    for k, v in c["defaults"].items():
        if v.startswith("http"):
            r.check(v in uris, f"{k} {v.rsplit('/', 1)[-1]} not offered by GetConfigurationOptions")


@test("X-PTZ-ORDER", "PTZConfiguration children come in schema order", "ptz", needs=("ptz",),
      clients=("frigate", "ha"), ref="onvif.xsd tt:PTZConfiguration (patch 0008's bug)")
def t_order(r):
    for c in r.d["ptz_cfgs"]:
        seen = [e for e in c["order"] if e in CFG_ORDER]
        idx = [CFG_ORDER.index(e) for e in seen]
        if idx != sorted(idx):
            bad = [seen[i + 1] for i in range(len(idx) - 1) if idx[i] > idx[i + 1]]
            r.check(False, f"{c['token']}: out of order at {bad}: zeep (Frigate, HA) drops those fields")
        else:
            r.info(f"{c['token']}: in order")


@test("PTZ-7-x-SPACES", "Generic spaces use the spec URIs and ranges", "ptz", needs=("ptz",),
      profiles=PT, ref="PTZ spec 5.7; PTZ-7-1-3..PTZ-7-4-4 (range part)")
def t_spaces(r):
    for kind, v in node(r)["spaces"].items():
        uri, xr, yr = GEN[kind]
        gen = [s for s in v if s["uri"] == uri]
        if v and not gen:
            r.check(False, f"{kind}: offered, but not the generic space {uri.rsplit('/', 1)[-1]}", else_warn=True)
        for s in gen:
            r.check(s["x"] == (float(xr[0]), float(xr[1])), f"{kind} XRange {s['x']}, spec {xr}")
            if yr:
                r.check(s["y"] == (float(yr[0]), float(yr[1])), f"{kind} YRange {s['y']}, spec {yr}")
        for s in v:
            if s["uri"] == FOV_SPACE:
                r.check(s["x"][0] is not None and s["x"][0] >= -1 and s["x"][1] <= 1,
                        f"TranslationSpaceFov range {s['x']}")


@test("X-PTZ-STATUS", "GetStatus: position, MoveStatus and UtcTime as capabilities promise", "ptz",
      needs=("ptz",), clients=("frigate", "ha"), profiles=PT, ref="PTZ spec 5.3.5")
def t_status(r):
    rep = r.ok("ptz", "GetStatus", f"<ProfileToken>{P(r)}</ProfileToken>")
    st = rep.x("tptz:PTZStatus")
    if not st:
        r.fail("no PTZStatus")
    s = st[0]
    r.check(xt(s, "tt:UtcTime"), "no UtcTime (mandatory)")
    pos = xp(s, "tt:Position")
    if r.f.get("ptz.cap.StatusPosition"):
        r.check(pos, "StatusPosition=true but no Position")
    ms = {k: xt(s, f"tt:MoveStatus/tt:{k}") for k in ("PanTilt", "Zoom")}
    if r.f.get("ptz.cap.MoveStatus"):
        r.check(ms["PanTilt"] in ("IDLE", "MOVING", "UNKNOWN"), f"MoveStatus/PanTilt is {ms['PanTilt']}")
    r.check(ms["PanTilt"] != "UNKNOWN", "MoveStatus UNKNOWN: Frigate cannot time its moves", else_warn=True)
    r.info(f"position pt=({xt(s, 'tt:Position/tt:PanTilt/@x')}, {xt(s, 'tt:Position/tt:PanTilt/@y')}) "
           f"zoom={xt(s, 'tt:Position/tt:Zoom/@x')}; move {ms}; error {xt(s, 'tt:Error')}")


@test("X-PTZ-PRESETS", "GetPresets", "ptz", needs=("ptz",), clients=("frigate", "ha"), profiles=PT,
      ref="PTZ spec 5.4.2")
def t_presets(r):
    rep = r.ok("ptz", "GetPresets", f"<ProfileToken>{P(r)}</ProfileToken>")
    ps = [(p.get("token"), xt(p, "tt:Name", "")) for p in rep.x("tptz:Preset")]
    r.check(len(ps) <= max(node(r)["max_presets"], 0) or not node(r)["max_presets"],
            f"{len(ps)} presets > MaximumNumberOfPresets {node(r)['max_presets']}", else_warn=True)
    r.info(f"{len(ps)}: " + ", ".join(f"{t}={n}" for t, n in ps[:20]) + (" ..." if len(ps) > 20 else ""))
    r.d["presets"] = ps


@test("X-PTZ-BADPROFILE", "PTZ calls with an invalid profile token fault", "ptz", needs=("ptz",),
      profiles=PT, ref="PTZ spec 5.3 (ter:NoProfile)")
def t_badprof(r):
    r.expect_fault(r.call("ptz", "GetStatus", "<ProfileToken>no_such_profile_xyz</ProfileToken>"),
                   "NoProfile", "InvalidArgVal")
    r.expect_fault(r.call("ptz", "Stop", "<ProfileToken>no_such_profile_xyz</ProfileToken>"),
                   "NoProfile", "InvalidArgVal")


@test("X-PTZ-UNSUPPORTED", "Operations the node does not offer fault, not silently succeed", "ptz",
      needs=("ptz",), profiles=PT, ref="PTZ test spec 4.x: ActionNotSupported for unsupported moves")
def t_unsupported(r):
    tried = 0
    if not r.f.get("ptz.abs.pt") and not r.f.get("ptz.abs.zoom"):
        tried += 1
        r.expect_fault(r.call("ptz", "AbsoluteMove", f"<ProfileToken>{P(r)}</ProfileToken><Position>"
                              '<tt:PanTilt x="0" y="0"/></Position>'), "ActionNotSupported", "NoPTZProfile")
    if not r.f.get("ptz.rel.pt") and not r.f.get("ptz.rel.zoom"):
        tried += 1
        r.expect_fault(r.call("ptz", "RelativeMove", f"<ProfileToken>{P(r)}</ProfileToken><Translation>"
                              '<tt:PanTilt x="0" y="0"/></Translation>'), "ActionNotSupported")
    if not r.f.get("ptz.home"):
        tried += 1
        r.expect_fault(r.call("ptz", "GotoHomePosition", f"<ProfileToken>{P(r)}</ProfileToken>"),
                       "ActionNotSupported", "NoHomePosition")
    if not tried:
        r.na("the node offers absolute, relative and home")


# ------------------------------------------------------------------ motion
def status(r):
    rep = r.call("ptz", "GetStatus", f"<ProfileToken>{P(r)}</ProfileToken>")
    if not rep.ok:
        return None
    s = rep.x("tptz:PTZStatus")[0]
    f = lambda p: (float(xt(s, p)) if xt(s, p) not in (None, "") else None)  # noqa: E731
    return {"x": f("tt:Position/tt:PanTilt/@x"), "y": f("tt:Position/tt:PanTilt/@y"),
            "z": f("tt:Position/tt:Zoom/@x"),
            "pt": xt(s, "tt:MoveStatus/tt:PanTilt"), "zm": xt(s, "tt:MoveStatus/tt:Zoom")}


def wait_idle(r, limit=20.0, axis="pt"):
    """-> (first MoveStatus, last, seconds)"""
    t0 = time.monotonic()
    first = last = (status(r) or {}).get(axis)
    while last == "MOVING" and time.monotonic() - t0 < limit:
        time.sleep(0.1)
        last = (status(r) or {}).get(axis)
    return first, last, time.monotonic() - t0


def stop(r):
    return r.call("ptz", "Stop", f"<ProfileToken>{P(r)}</ProfileToken><PanTilt>true</PanTilt><Zoom>true</Zoom>")


def cont(r, x=0.0, y=0.0, z=None):
    v = f'<tt:PanTilt x="{x}" y="{y}"/>' if z is None else f'<tt:Zoom x="{z}"/>'
    return r.call("ptz", "ContinuousMove", f"<ProfileToken>{P(r)}</ProfileToken><Velocity>{v}</Velocity>")


@test("PTZ-3-1-5", "ContinuousMove pan/tilt and Stop (matched, returns)", "ptz", cat=MOVE,
      needs=("ptz", "ptz.cont.pt"), clients=("frigate", "ha"), profiles=PT)
def t_cont(r):
    for label, x, y in (("right", 0.5, 0), ("left", -0.5, 0), ("up", 0, 0.5), ("down", 0, -0.5)):
        rep = cont(r, x, y)
        if not r.check(rep.ok, f"ContinuousMove {label}: {rep.why()}"):
            continue
        time.sleep(0.4)
        mid = status(r) or {}
        time.sleep(0.6)
        sp = stop(r)
        r.check(sp.ok, f"Stop: {sp.why()}")
        first, last, secs = wait_idle(r, 5)
        if r.f.get("ptz.cap.MoveStatus"):
            r.check(mid.get("pt") == "MOVING", f"{label}: MoveStatus during the move is {mid.get('pt')}", else_warn=True)
            r.check(last == "IDLE", f"{label}: MoveStatus {last} {secs:.1f} s after Stop")
        r.info(f"{label}: during {mid.get('pt')}, IDLE {secs:.2f} s after Stop")
        time.sleep(0.5)


@test("X-PTZ-CONT-ZOOM", "ContinuousMove zoom and Stop (matched, returns)", "ptz", cat=MOVE,
      needs=("ptz", "ptz.cont.zoom"), clients=("frigate", "ha"), profiles=PT, ref="PTZ-3-1-4/5 zoom part")
def t_contz(r):
    z0 = (status(r) or {}).get("z")
    for label, z in (("in", 0.5), ("out", -0.5)):
        before = (status(r) or {}).get("z")
        rep = cont(r, z=z)
        if not r.check(rep.ok, f"zoom {label}: {rep.why()}"):
            continue
        time.sleep(1.0)
        r.check(stop(r).ok, "Stop failed")
        t0 = time.monotonic()
        _, last, _ = wait_idle(r, 6, "zm")
        # the reported position must follow the move: Frigate reads it every poll
        now = before
        while time.monotonic() - t0 < 4:
            now = (status(r) or {}).get("z")
            if before is not None and now is not None and (now - before) * z > 0.01:
                break
            time.sleep(0.2)
        lag = time.monotonic() - t0
        if before is not None and now is not None:
            r.check((now - before) * z > 0.01 or (z < 0 and before < 0.01),
                    f"zoom {label}: GetStatus zoom {before} -> {now}, not moved after {lag:.1f} s "
                    "(stale position)", else_warn=True)
        r.info(f"zoom {label}: {before} -> {now}, position updated {lag:.1f} s after Stop "
               f"(Zoom MoveStatus {last})")
        time.sleep(0.5)
    r.info(f"zoom before {z0}, after {(status(r) or {}).get('z')}")


def rel(r, x, y, space=None, speed=1.0, zoom=None):
    sp = f' space="{space}"' if space else ""
    tr = f'<tt:PanTilt x="{x}" y="{y}"{sp}/>' + (f'<tt:Zoom x="{zoom}"/>' if zoom is not None else "")
    return r.call("ptz", "RelativeMove", f"<ProfileToken>{P(r)}</ProfileToken><Translation>{tr}</Translation>"
                  f'<Speed><tt:PanTilt x="{speed}" y="{speed}"/></Speed>')


@test("PTZ-3-1-3", "RelativeMove in the generic space (matched, returns)", "ptz", cat=MOVE,
      needs=("ptz", "ptz.rel.pt"), clients=("ha",), profiles=PT)
def t_rel(r):
    gen = SPACES + "PanTiltSpaces/TranslationGenericSpace"
    has = any(s["uri"] == gen for s in node(r)["spaces"]["RelativePanTiltTranslationSpace"])
    if not has:
        r.na("no generic translation space (only " + ", ".join(
            s["uri"].rsplit("/", 1)[-1] for s in node(r)["spaces"]["RelativePanTiltTranslationSpace"]) + ")")
    for x, y in ((0.1, 0), (-0.1, 0)):
        rep = rel(r, x, y, gen)
        r.check(rep.ok, f"RelativeMove {x},{y}: {rep.why()}")
        first, last, secs = wait_idle(r, 15)
        r.info(f"{x:+},{y:+}: MoveStatus {first} -> {last} in {secs:.2f} s")


@test("X-PTZ-REL-FOV", "RelativeMove in the FOV space: MOVING right after the call, then IDLE",
      "ptz", cat=MOVE, needs=("ptz", "ptz.rel.pt.fov"), clients=("frigate",),
      ref="Frigate autotracking (ptz/onvif.py, autotrack.py)")
def t_relfov(r):
    for label, x, y in (("right 0.2", 0.2, 0), ("left 0.2", -0.2, 0), ("up 0.2", 0, 0.2), ("down 0.2", 0, -0.2),
                        ("diag +0.3/+0.1", 0.3, 0.1), ("diag -0.3/-0.1", -0.3, -0.1)):
        t0 = time.monotonic()
        rep = rel(r, x, y, FOV_SPACE)
        if not r.check(rep.ok, f"{label}: {rep.why()}"):
            continue
        first, last, secs = wait_idle(r, 15)
        good = first == "MOVING" and last == "IDLE"
        r.check(good, f"{label}: MoveStatus {first} -> {last} after {secs:.2f} s "
                      "(Frigate times each move by polling MOVING until IDLE)")
        r.info(f"{label}: call {rep.elapsed * 1000:.0f} ms, {first} -> {last} {time.monotonic() - t0:.2f} s")
        time.sleep(0.5)


@test("PTZ-3-1-1", "AbsoluteMove pan/tilt and back (needs StatusPosition)", "ptz", cat=MOVE,
      needs=("ptz", "ptz.abs.pt", "ptz.cap.StatusPosition"), clients=("ha",), profiles=PT)
def t_abs(r):
    s0 = status(r)
    if not s0 or s0["x"] is None:
        r.na("no position to return to")
    tgt = (max(-1, min(1, s0["x"] + 0.05)), s0["y"])
    for x, y in (tgt, (s0["x"], s0["y"])):
        rep = r.call("ptz", "AbsoluteMove", f"<ProfileToken>{P(r)}</ProfileToken><Position>"
                     f'<tt:PanTilt x="{x}" y="{y}"/></Position>')
        r.check(rep.ok, f"AbsoluteMove {x:.3f},{y:.3f}: {rep.why()}")
        wait_idle(r, 20)
        s = status(r) or {}
        if s.get("x") is not None:
            r.check(abs(s["x"] - x) < 0.02 and abs(s["y"] - y) < 0.02,
                    f"asked {x:.3f},{y:.3f}, at {s['x']:.3f},{s['y']:.3f}", else_warn=True)


@test("X-PTZ-ABS-ZOOM", "AbsoluteMove zoom and back", "ptz", cat=MOVE,
      needs=("ptz", "ptz.abs.zoom"), clients=("frigate", "ha"), ref="PTZ-7-1-4; Frigate zooming: absolute")
def t_absz(r):
    s0 = status(r) or {}
    z0 = s0.get("z")
    if z0 is None:
        r.na("GetStatus reports no zoom position")
    tgt = 0.1 if z0 < 0.5 else z0 - 0.1
    for z in (tgt, z0):
        t0 = time.monotonic()
        # Frigate's form: Position/Zoom only, no PanTilt, no space; Speed/Zoom 1
        rep = r.call("ptz", "AbsoluteMove", f"<ProfileToken>{P(r)}</ProfileToken><Position>"
                     f'<tt:Zoom x="{z:.3f}"/></Position><Speed><tt:Zoom x="1"/></Speed>')
        r.check(rep.ok, f"zoom to {z:.3f}: {rep.why()}")
        _, last, _ = wait_idle(r, 20, "zm")
        wait_idle(r, 20)
        s = status(r) or {}
        got = s.get("z")
        r.check(got is not None and abs(got - z) < 0.03, f"zoom asked {z:.3f}, at {got}", else_warn=True)
        if s0.get("x") is not None and s.get("x") is not None:
            r.check(abs(s["x"] - s0["x"]) < 0.01 and abs(s["y"] - s0["y"]) < 0.01,
                    f"a zoom-only AbsoluteMove moved pan/tilt ({s0['x']:.3f},{s0['y']:.3f}) -> "
                    f"({s['x']:.3f},{s['y']:.3f})")
        r.info(f"zoom {z:.3f}: at {got} after {time.monotonic() - t0:.1f} s")


@test("PTZ-3-1-2", "AbsoluteMove out of range faults (and does not move)", "ptz", cat=MOVE,
      needs=("ptz", "ptz.abs.pt"), profiles=PT, ref="ter:InvalidPosition")
def t_abs_bad(r):
    rep = r.call("ptz", "AbsoluteMove", f"<ProfileToken>{P(r)}</ProfileToken><Position>"
                 '<tt:PanTilt x="5" y="5"/></Position>')
    if rep.ok:
        stop(r)
    r.expect_fault(rep, "InvalidPosition", "InvalidArgVal")


@test("PTZ-5-1-1", "GotoHomePosition (head ends at home)", "ptz", cat=MOVE, needs=("ptz", "ptz.home"),
      clients=("ha",), profiles=PT)
def t_home(r):
    rep = r.call("ptz", "GotoHomePosition", f"<ProfileToken>{P(r)}</ProfileToken>")
    if not r.check(rep.ok, f"GotoHomePosition: {rep.why()}"):
        return
    first, last, secs = wait_idle(r, 30)
    r.info(f"MoveStatus {first} -> {last} in {secs:.1f} s; the head is now at home")


@test("PTZ-4-1-5", "GotoPreset to an existing preset", "ptz", cat=MOVE, needs=("ptz", "ptz.presets"),
      clients=("frigate", "ha"), profiles=PT)
def t_goto(r):
    rep = r.ok("ptz", "GetPresets", f"<ProfileToken>{P(r)}</ProfileToken>")
    ps = rep.x("tptz:Preset/@token")
    want = getattr(r.ctx.args, "preset", None)
    if want:
        ps = [p for p in ps if p == want] or r.na(f"preset {want} not listed")
    elif not ps:
        r.na("no presets stored")
    elif "home" in ps:
        ps = ["home"]
    tok = ps[0]
    rep = r.call("ptz", "GotoPreset", f"<ProfileToken>{P(r)}</ProfileToken><PresetToken>{tok}</PresetToken>")
    r.check(rep.ok, f"GotoPreset {tok}: {rep.why()}")
    first, last, secs = wait_idle(r, 30)
    r.info(f"GotoPreset {tok}: MoveStatus {first} -> {last} in {secs:.1f} s")
    r.expect_fault(r.call("ptz", "GotoPreset", f"<ProfileToken>{P(r)}</ProfileToken>"
                          "<PresetToken>no_such_preset_xyz</PresetToken>"), "NoToken", "InvalidArgVal",
                   what="GotoPreset invalid token")


@test("PTZ-4-1-4", "SetPreset, GetPresets, RemovePreset round trip", "ptz", cat=PRESET,
      needs=("ptz", "ptz.presets"), clients=("ha",), profiles=PT,
      ref="PTZ-4-1-4/4-1-6. Caution: a board may store positions it does not list")
def t_setpreset(r):
    name = "onvifcheck"
    rep = r.ok("ptz", "SetPreset", f"<ProfileToken>{P(r)}</ProfileToken><PresetName>{name}</PresetName>")
    tok = rep.t("tptz:PresetToken")
    r.check(tok, "SetPresetResponse has no PresetToken")
    lst = r.ok("ptz", "GetPresets", f"<ProfileToken>{P(r)}</ProfileToken>")
    r.check(tok in lst.x("tptz:Preset/@token"), f"new preset {tok} not listed")
    r.check(name in lst.x("tptz:Preset/tt:Name/text()"), "new preset's name not listed", else_warn=True)
    rm = r.call("ptz", "RemovePreset", f"<ProfileToken>{P(r)}</ProfileToken><PresetToken>{tok}</PresetToken>")
    r.check(rm.ok, f"RemovePreset: {rm.why()}")
    lst = r.ok("ptz", "GetPresets", f"<ProfileToken>{P(r)}</ProfileToken>")
    r.check(tok not in lst.x("tptz:Preset/@token"), f"preset {tok} still listed after RemovePreset")
    r.info(f"preset {tok} set and removed")
