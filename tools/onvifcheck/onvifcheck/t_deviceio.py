"""DeviceIO and relay tests. Toggling a relay drives real hardware (IR or
white LEDs on Thingino), so that one is a CONFIG test and restores state."""
from __future__ import annotations

import time

from .core import CONFIG, test
from .soap import xp, xt


@test("X-DIO-CAPS", "DeviceIO GetServiceCapabilities", "deviceio", needs=("svc.deviceio",))
def t_caps(r):
    rep = r.ok("deviceio", "GetServiceCapabilities")
    cap = rep.x("tmd:Capabilities")
    if cap:
        r.info(" ".join(f"{k}={v}" for k, v in cap[0].attrib.items()))


@test("DEVICEIO-7-1-1", "DeviceIO GetVideoSources", "deviceio", needs=("svc.deviceio",))
def t_vs(r):
    rep = r.ok("deviceio", "GetVideoSources")
    toks = rep.x("tmd:Token/text()")
    r.info(f"tokens {toks}")
    if r.d.get("vs_token"):
        r.check(r.d["vs_token"] in toks, f"media source {r.d['vs_token']} not among {toks}", else_warn=True)


@test("DEVICEIO-4-1-1", "DeviceIO GetAudioSources", "deviceio", needs=("svc.deviceio",))
def t_as(r):
    rep = r.call("deviceio", "GetAudioSources")
    if rep.fault and rep.fault.has("ActionNotSupported"):
        r.na("ActionNotSupported")
    r.check(rep.ok, rep.why())
    r.info(f"tokens {rep.x('tmd:Token/text()')}")


@test("DEVICE-5-1-1", "GetRelayOutputs (device and DeviceIO agree)", "deviceio", clients=("ha",))
def t_relays(r):
    a = r.call("device", "GetRelayOutputs")
    b = r.call("deviceio", "GetRelayOutputs") if r.f.get("svc.deviceio") else None
    ta = a.x("tds:RelayOutputs/@token") if a.ok else []
    tb = b.x("tmd:RelayOutputs/@token") if b is not None and b.ok else []
    if not ta and not tb:
        r.na("no relay outputs")
    if b is not None:
        r.check(sorted(ta) == sorted(tb), f"device lists {ta}, DeviceIO lists {tb}", else_warn=True)
    for ro in (a.x("tds:RelayOutputs") if a.ok else []):
        r.info(f"{ro.get('token')}: mode {xt(ro, 'tt:Properties/tt:Mode')}, idle {xt(ro, 'tt:Properties/tt:IdleState')}, "
               f"delay {xt(ro, 'tt:Properties/tt:DelayTime')}")


@test("X-DIO-RELAY-TOGGLE", "SetRelayOutputState on each relay (restored)", "deviceio", cat=CONFIG,
      needs=("relays",), clients=("ha",), ref="DEVICE-5-1-5/6")
def t_toggle(r):
    want = getattr(r.ctx.args, "relay", None)
    for tok in r.d["relays"]:
        if want and tok != want:
            continue
        for st in ("active", "inactive"):
            rep = r.call("device", "SetRelayOutputState",
                         f"<RelayOutputToken>{tok}</RelayOutputToken><LogicalState>{st}</LogicalState>")
            r.check(rep.ok, f"{tok} {st}: {rep.why()}")
            time.sleep(1.0)
        r.info(f"{tok}: active then inactive (check the hardware followed)")
