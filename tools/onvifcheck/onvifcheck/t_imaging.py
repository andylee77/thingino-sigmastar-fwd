"""Imaging tests, including whether a setting the camera accepts actually
changes the picture (catches settings that are advertised but go nowhere)."""
from __future__ import annotations

import io
import time

from . import net
from .core import CONFIG, MOVE, test
from .soap import xp, xt

IMG = ("S", "T")


def VS(r):
    return r.d.get("vs_token") or r.na("no video source token")


@test("IMAGING-3-1-1", "Imaging GetServiceCapabilities", "imaging", needs=("svc.imaging",), profiles=("T",),
      clients=("frigate",))
def t_caps(r):
    rep = r.ok("imaging", "GetServiceCapabilities")
    cap = rep.x("timg:Capabilities")
    r.check(cap, "no Capabilities")
    if cap:
        r.info(" ".join(f"{k}={v}" for k, v in cap[0].attrib.items()) or "no attributes")


@test("IMAGING-1-1-1", "GetImagingSettings", "imaging", needs=("svc.imaging",), clients=("ha", "frigate"),
      profiles=("T",))
def t_get(r):
    rep = r.ok("imaging", "GetImagingSettings", f"<VideoSourceToken>{VS(r)}</VideoSourceToken>")
    s = rep.x("timg:ImagingSettings")
    r.check(s, "no ImagingSettings")
    if s:
        r.info(", ".join(f"{e.tag.rsplit('}', 1)[-1]}={(e.text or '').strip() or '{..}'}" for e in s[0]))


@test("IMAGING-1-1-3", "GetOptions", "imaging", needs=("svc.imaging",), clients=("ha",), profiles=("T",))
def t_opts(r):
    rep = r.ok("imaging", "GetOptions", f"<VideoSourceToken>{VS(r)}</VideoSourceToken>")
    o = rep.x("timg:ImagingOptions")
    r.check(o, "no ImagingOptions")
    if o:
        r.info(", ".join(e.tag.rsplit("}", 1)[-1] for e in o[0]))


@test("IMAGING-1-1-16", "Settings lie inside the options", "imaging", needs=("svc.imaging",), profiles=("T",))
def t_consistent(r):
    s = r.ok("imaging", "GetImagingSettings", f"<VideoSourceToken>{VS(r)}</VideoSourceToken>")
    o = r.ok("imaging", "GetOptions", f"<VideoSourceToken>{VS(r)}</VideoSourceToken>")
    for k in ("Brightness", "ColorSaturation", "Contrast", "Sharpness"):
        v = s.t(f"timg:ImagingSettings/tt:{k}")
        lo, hi = o.t(f"timg:ImagingOptions/tt:{k}/tt:Min"), o.t(f"timg:ImagingOptions/tt:{k}/tt:Max")
        if v is None:
            r.check(lo is None, f"{k}: options offer {lo}..{hi} but the settings omit it", else_warn=True)
            continue
        r.check(lo is not None and float(lo) <= float(v) <= float(hi), f"{k}={v} outside {lo}..{hi}")
    ir = s.t("timg:ImagingSettings/tt:IrCutFilter")
    if ir:
        modes = o.x("timg:ImagingOptions/tt:IrCutFilterModes/text()")
        r.check(ir in modes, f"IrCutFilter {ir} not among {modes}")
        r.info(f"IR-cut {ir} of {modes}")


@test("IMAGING-1-1-10", "GetImagingSettings with an invalid token faults", "imaging", needs=("svc.imaging",),
      profiles=("T",))
def t_badtok(r):
    r.expect_fault(r.call("imaging", "GetImagingSettings", "<VideoSourceToken>no_such_vs_xyz</VideoSourceToken>"),
                   "NoSource", "InvalidArgVal")


@test("IMAGING-2-1-1", "GetMoveOptions (focus)", "imaging", needs=("svc.imaging",), clients=("ha",),
      profiles=("T",))
def t_moveopts(r):
    rep = r.call("imaging", "GetMoveOptions", f"<VideoSourceToken>{VS(r)}</VideoSourceToken>")
    if rep.fault and rep.fault.has("ActionNotSupported", "NoImagingForSource"):
        r.na(f"no focus control ({rep.fault})")
    if not rep.ok:
        r.fail(rep.why())
    mo = rep.x("timg:MoveOptions/*")
    r.info("focus moves: " + (", ".join(m.tag.rsplit("}", 1)[-1] for m in mo) or "none"))


@test("IMAGING-2-1-11", "Imaging GetStatus (focus position)", "imaging", needs=("svc.imaging",),
      profiles=("T",))
def t_status(r):
    rep = r.call("imaging", "GetStatus", f"<VideoSourceToken>{VS(r)}</VideoSourceToken>")
    if rep.fault and rep.fault.has("ActionNotSupported"):
        r.na("ActionNotSupported")
    if not rep.ok:
        r.fail(rep.why())
    r.info(f"focus position {rep.t('.//tt:FocusStatus20/tt:Position')}, "
           f"move {rep.t('.//tt:FocusStatus20/tt:MoveStatus')}")


@test("IMAGING-2-1-7", "Focus ContinuousMove and Stop", "imaging", cat=MOVE,
      needs=("svc.imaging", "imaging.focus.continuous"), clients=("ha",), profiles=("T",))
def t_focus(r):
    for sp in (0.5, -0.5):
        rep = r.call("imaging", "Move", f"<VideoSourceToken>{VS(r)}</VideoSourceToken><Focus>"
                     f'<tt:Continuous><tt:Speed>{sp}</tt:Speed></tt:Continuous></Focus>')
        r.check(rep.ok, f"focus continuous {sp}: {rep.why()}")
        time.sleep(0.5)
        r.check(r.call("imaging", "Stop", f"<VideoSourceToken>{VS(r)}</VideoSourceToken>").ok, "Stop failed")
        time.sleep(0.3)


def _luma(r):
    """Mean luminance of a snapshot, or None (needs Pillow)."""
    try:
        from PIL import Image, ImageStat
    except ImportError:
        return None
    toks = [p for p in r.d.get("profiles", [])]
    if not toks:
        return None
    rep = r.call("media", "GetSnapshotUri", f"<ProfileToken>{toks[-1]['token']}</ProfileToken>")
    if not rep.ok:
        return None
    s = net.snapshot(rep.t("trt:MediaUri/tt:Uri", ""), r.ctx.user, r.ctx.password)
    if not s.data:
        return None
    return ImageStat.Stat(Image.open(io.BytesIO(s.data)).convert("L")).mean[0]


@test("X-IMG-EFFECT", "SetImagingSettings Brightness reads back AND changes the picture (restored)",
      "imaging", cat=CONFIG, needs=("svc.imaging", "imaging.options"), clients=("ha",), profiles=("T",),
      ref="IMAGING-1-1-14 plus a snapshot luminance check")
def t_effect(r):
    vs = VS(r)
    s = r.ok("imaging", "GetImagingSettings", f"<VideoSourceToken>{vs}</VideoSourceToken>")
    o = r.ok("imaging", "GetOptions", f"<VideoSourceToken>{vs}</VideoSourceToken>")
    b0 = s.t("timg:ImagingSettings/tt:Brightness")
    lo = o.t("timg:ImagingOptions/tt:Brightness/tt:Min")
    hi = o.t("timg:ImagingOptions/tt:Brightness/tt:Max")
    if b0 is None or lo is None:
        r.na("no Brightness setting/option")
    b0, lo, hi = float(b0), float(lo), float(hi)
    l0 = _luma(r)
    tgt = lo if b0 - lo > hi - b0 else hi

    def setb(v):
        return r.call("imaging", "SetImagingSettings", f"<VideoSourceToken>{vs}</VideoSourceToken>"
                      f"<ImagingSettings><tt:Brightness>{v:g}</tt:Brightness></ImagingSettings>"
                      "<ForcePersistence>false</ForcePersistence>")
    try:
        rep = setb(tgt)
        if not r.check(rep.ok, f"SetImagingSettings Brightness {tgt:g}: {rep.why()}"):
            return
        time.sleep(2.0)
        back = r.ok("imaging", "GetImagingSettings", f"<VideoSourceToken>{vs}</VideoSourceToken>")
        got = back.t("timg:ImagingSettings/tt:Brightness")
        r.check(got is not None and abs(float(got) - tgt) < 1e-6, f"set {tgt:g}, reads back {got}")
        l1 = _luma(r)
        if l0 is None or l1 is None:
            r.info("no luminance check (pip install pillow, and a working snapshot)")
        else:
            moved = abs(l1 - l0)
            r.check(moved > 8, f"Brightness {b0:g} -> {tgt:g} moved snapshot luma only {l0:.0f} -> {l1:.0f}: "
                               "accepted but no effect on the picture")
            r.info(f"brightness {b0:g} -> {tgt:g}: luma {l0:.0f} -> {l1:.0f}")
    finally:
        rep = setb(b0)
        r.check(rep.ok, f"restore Brightness {b0:g}: {rep.why()}")
