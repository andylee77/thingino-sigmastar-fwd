"""Media (ver10) and Media2 (ver20) tests, plus checks that the advertised
streams and snapshots are really served (RTSP DESCRIBE, HTTP GET)."""
from __future__ import annotations

from . import net
from .core import test
from .soap import xp, xt

SDP_CODEC = {"H264": "H264", "H265": "H265", "JPEG": "JPEG", "MPEG4": "MP4V-ES"}


def _profiles(r):
    p = r.d.get("profiles") or []
    if not p:
        r.fail("GetProfiles returned no profiles")
    return p


@test("MEDIA-8-1-1", "Media GetServiceCapabilities", "media", needs=("svc.media",), profiles=("S",))
def t_caps(r):
    rep = r.ok("media", "GetServiceCapabilities")
    cap = rep.x("trt:Capabilities")
    r.check(cap, "no Capabilities element")
    if cap:
        r.info(" ".join(f"{k}={v}" for k, v in cap[0].attrib.items()))
        pc = xp(cap[0], "trt:ProfileCapabilities/@MaximumNumberOfProfiles")
        sc = xp(cap[0], "trt:StreamingCapabilities")
        r.info(f"max profiles {pc[0] if pc else '?'}; streaming {dict(sc[0].attrib) if sc else '?'}")


@test("MEDIA-1-1-1", "GetProfiles: ready-to-use profiles with video", "media", needs=("svc.media",),
      clients=("frigate", "ha", "go2rtc"), profiles=("S",))
def t_profiles(r):
    rep = r.ok("media", "GetProfiles")
    ps = rep.x("trt:Profiles")
    if not ps:
        r.fail("no profiles")
    for p in ps:
        tok = p.get("token")
        vsc = xp(p, "tt:VideoSourceConfiguration")
        vec = xp(p, "tt:VideoEncoderConfiguration")
        r.check(vsc, f"{tok}: no VideoSourceConfiguration")
        r.check(vec, f"{tok}: no VideoEncoderConfiguration (not ready to stream)")
        enc = xt(p, "tt:VideoEncoderConfiguration/tt:Encoding")
        w = xt(p, "tt:VideoEncoderConfiguration/tt:Resolution/tt:Width")
        h = xt(p, "tt:VideoEncoderConfiguration/tt:Resolution/tt:Height")
        fps = xt(p, "tt:VideoEncoderConfiguration/tt:RateControl/tt:FrameRateLimit")
        br = xt(p, "tt:VideoEncoderConfiguration/tt:RateControl/tt:BitrateLimit")
        extra = []
        if xp(p, "tt:AudioEncoderConfiguration"):
            extra.append("audio " + (xt(p, "tt:AudioEncoderConfiguration/tt:Encoding") or "?"))
        if xp(p, "tt:PTZConfiguration"):
            extra.append("PTZ " + (xt(p, "tt:PTZConfiguration/@token") or ""))
        if xp(p, "tt:MetadataConfiguration"):
            extra.append("metadata")
        if xp(p, "tt:Extension/tt:AudioOutputConfiguration"):
            extra.append("audio out")
        r.info(f"{tok} '{xt(p, 'tt:Name')}' fixed={p.get('fixed')}: {enc} {w}x{h} {fps} fps "
               f"{br} kb/s {'; '.join(extra)}")
    r.check(any(xt(p, "tt:VideoEncoderConfiguration/tt:Encoding") == "H264" for p in ps),
            "no H264 profile (Frigate picks its PTZ profile among H264 ones)", else_warn=True)


@test("MEDIA-2-2-5", "Video sources match the profiles' source tokens", "media", needs=("svc.media",),
      profiles=("S",))
def t_sources(r):
    rep = r.ok("media", "GetVideoSources")
    toks = rep.x("trt:VideoSources/@token")
    r.check(toks, "no video sources")
    for p in _profiles(r):
        r.check(p["vs"] in toks, f"profile {p['token']} uses source {p['vs']}, not in GetVideoSources {toks}")
    for v in rep.x("trt:VideoSources"):
        r.info(f"{v.get('token')}: {xt(v, 'tt:Resolution/tt:Width')}x{xt(v, 'tt:Resolution/tt:Height')} "
               f"@ {xt(v, 'tt:Framerate')}; imaging {'yes' if xp(v, 'tt:Imaging') else 'no'}")


@test("MEDIA-2-3-1", "Encoder configurations match the profiles", "media", needs=("svc.media",),
      profiles=("S",))
def t_encs(r):
    rep = r.ok("media", "GetVideoEncoderConfigurations")
    toks = rep.x("trt:Configurations/@token")
    for p in _profiles(r):
        if p["venc"]:
            r.check(p["venc"] in toks, f"profile {p['token']} encoder {p['venc']} not listed")
    for c in rep.x("trt:Configurations"):
        uc = xt(c, "tt:UseCount")
        r.info(f"{c.get('token')} use {uc}: {xt(c, 'tt:Encoding')} "
               f"{xt(c, 'tt:Resolution/tt:Width')}x{xt(c, 'tt:Resolution/tt:Height')} "
               f"GOP {xt(c, 'tt:H264/tt:GovLength')} {xt(c, 'tt:H264/tt:H264Profile') or ''}")


@test("MEDIA-2-1-2", "Each encoder's settings lie inside its options", "media", needs=("svc.media",),
      profiles=("S",))
def t_encopts(r):
    for p in _profiles(r):
        if not p["venc"]:
            continue
        rep = r.call("media", "GetVideoEncoderConfigurationOptions",
                     f"<ConfigurationToken>{p['venc']}</ConfigurationToken><ProfileToken>{p['token']}</ProfileToken>")
        if not r.check(rep.ok, f"{p['venc']}: {rep.why()}"):
            continue
        enc = p["encoding"]
        blk = {"H264": "H264", "JPEG": "JPEG", "MPEG4": "MPEG4"}.get(enc)
        if not blk:
            # H265 lives in the options' Extension (Media1 has no H265 element)
            r.info(f"{p['token']}: {enc} (Media1 has no H265 options block)")
            continue
        res = [(int(xt(x, "tt:Width", "0")), int(xt(x, "tt:Height", "0")))
               for x in rep.x(f"trt:Options/tt:{blk}/tt:ResolutionsAvailable")]
        r.check((p["width"], p["height"]) in res,
                f"{p['token']}: {p['width']}x{p['height']} not among the {blk} options {res}")
        fr = (xt(rep.body, f"trt:Options/tt:{blk}/tt:FrameRateRange/tt:Min"),
              xt(rep.body, f"trt:Options/tt:{blk}/tt:FrameRateRange/tt:Max"))
        if p["fps"] and fr[0] and fr[1]:
            r.check(float(fr[0]) <= float(p["fps"]) <= float(fr[1]),
                    f"{p['token']}: {p['fps']} fps outside {fr}")
        r.info(f"{p['token']}: {len(res)} resolutions, fps {fr[0]}-{fr[1]}")


@test("MEDIA-2-2-3", "Video source configuration options", "media", needs=("svc.media",), profiles=("S",))
def t_vscopts(r):
    p = _profiles(r)[0]
    rep = r.ok("media", "GetVideoSourceConfigurationOptions",
               f"<ConfigurationToken>{p['vsc']}</ConfigurationToken><ProfileToken>{p['token']}</ProfileToken>")
    r.check(rep.x("trt:Options/tt:BoundsRange"), "no BoundsRange")


@test("X-MEDIA-URI", "GetStreamUri for every profile, and the RTSP server answers DESCRIBE", "media",
      needs=("svc.media",), clients=("frigate", "ha", "go2rtc"), profiles=("S",),
      ref="Media 5.15.1; Streaming spec 5.1 (RTSS-1-1-43 is the full streaming test)")
def t_uri(r):
    for p in _profiles(r):
        rep = r.call("media", "GetStreamUri",
                     "<StreamSetup><tt:Stream>RTP-Unicast</tt:Stream><tt:Transport><tt:Protocol>RTSP</tt:Protocol>"
                     f"</tt:Transport></StreamSetup><ProfileToken>{p['token']}</ProfileToken>")
        if not r.check(rep.ok, f"{p['token']} GetStreamUri: {rep.why()}"):
            continue
        uri = rep.t("trt:MediaUri/tt:Uri", "")
        r.check(uri.startswith("rtsp://"), f"{p['token']}: URI {uri} is not rtsp://")
        inv = rep.t("trt:MediaUri/tt:InvalidAfterConnect")
        r.check(inv is not None, f"{p['token']}: MediaUri lacks InvalidAfterConnect")
        d = net.rtsp_describe(uri, r.ctx.user, r.ctx.password)
        if d.error or d.status != 200:
            r.check(False, f"{p['token']}: DESCRIBE {uri} -> {d.error or f'{d.status} {d.reason}'}")
            continue
        media = d.media()
        vid = [m for m in media if m[0] == "video"]
        aud = [m for m in media if m[0] == "audio"]
        want = SDP_CODEC.get(p["encoding"] or "", p["encoding"])
        r.check(vid and want and want.upper() in (vid[0][1] or "").upper(),
                f"{p['token']}: SDP video {vid[0][1] if vid else None}, profile says {p['encoding']}")
        if p["aenc"]:
            r.check(aud, f"{p['token']}: profile advertises {p['aenc']} audio, the SDP has none "
                         "(clients that negotiate audio will wait or fail)", else_warn=True)
        r.info(f"{p['token']}: {uri.split('@')[-1]} -> {d.auth_scheme or 'no'} auth, "
               + ", ".join(f"{k} {c}" for k, c, _ in media))
        r.d.setdefault("stream_uris", {})[p["token"]] = uri


@test("MEDIA-6-1-1", "GetSnapshotUri and the snapshot is a JPEG of the profile's size", "media",
      needs=("svc.media",), clients=("ha", "frigate"), profiles=("S",))
def t_snapshot(r):
    for p in _profiles(r):
        rep = r.call("media", "GetSnapshotUri", f"<ProfileToken>{p['token']}</ProfileToken>")
        if not rep.ok:
            r.check(not r.f.get("snapshot"), f"{p['token']}: GetSnapshotUri {rep.why()} "
                                             "(capabilities say SnapshotUri=true)")
            continue
        uri = rep.t("trt:MediaUri/tt:Uri", "")
        s = net.snapshot(uri, r.ctx.user, r.ctx.password)
        if not r.check(s.status == 200 and s.width, f"{p['token']}: GET {uri} -> {s.error or s.status} "
                                                    f"{s.ctype} {s.size} B"):
            continue
        r.info(f"{p['token']}: {s.width}x{s.height} JPEG {s.size // 1024} KB, auth {s.auth}")
        if p["width"] and (s.width, s.height) != (p["width"], p["height"]):
            r.info(f"{p['token']}: snapshot size differs from the stream ({p['width']}x{p['height']})")


@test("X-MEDIA-AUDIO", "Advertised audio sources/outputs exist", "media", needs=("svc.media", "audio"),
      clients=("ha",), profiles=("S", "T"))
def t_audio(r):
    rep = r.call("media", "GetAudioSources")
    src = rep.x("trt:AudioSources/@token") if rep.ok else []
    r.check(src, f"profiles carry audio but GetAudioSources: {rep.why() if not rep.ok else 'empty'}")
    rep = r.call("media", "GetAudioOutputs")
    out = rep.x("trt:AudioOutputs/@token") if rep.ok else []
    if r.f.get("backchannel"):
        r.check(out, "a profile has an audio output but GetAudioOutputs lists no output token")
    r.info(f"audio sources {src}, outputs {out}; whether audio is really streamed is X-MEDIA-URI's SDP check")


@test("MEDIA-1-1-x-FAULT", "GetProfile with an invalid token faults", "media", needs=("svc.media",),
      profiles=("S",), ref="Media 5.2.3 (ter:InvalidArgVal/ter:NoProfile)")
def t_badprofile(r):
    rep = r.call("media", "GetProfile", "<ProfileToken>no_such_profile_xyz</ProfileToken>")
    r.expect_fault(rep, "NoProfile", "InvalidArgVal")


# ------------------------------------------------------------------ Media2
@test("MEDIA2-7-1-1", "Media2 GetServiceCapabilities", "media2", needs=("svc.media2",), profiles=("T", "M"))
def t2_caps(r):
    rep = r.ok("media2", "GetServiceCapabilities")
    cap = rep.x("tr2:Capabilities")
    r.check(cap, "no Capabilities")
    if cap:
        r.info(" ".join(f"{k}={v}" for k, v in cap[0].attrib.items()))


@test("X-MEDIA2-PRESENT", "Media2 is present when Profile T is claimed", "media2", profiles=("T",))
def t2_present(r):
    if not r.f.get("claims.T"):
        r.na("Profile T not claimed")
    r.check(r.f.get("svc.media2"), "Profile T claimed, but GetServices lists no Media2 service")


@test("MEDIA2-1-1-4", "Media2 GetProfiles", "media2", needs=("svc.media2",), profiles=("T", "M"))
def t2_profiles(r):
    rep = r.ok("media2", "GetProfiles", "<Type>All</Type>")
    ps = rep.x("tr2:Profiles")
    r.check(ps, "no profiles")
    for p in ps:
        r.info(f"{p.get('token')}: {xt(p, 'tr2:Configurations/tr2:VideoEncoder/tt:Encoding')} "
               f"{xt(p, 'tr2:Configurations/tr2:VideoEncoder/tt:Resolution/tt:Width')}x"
               f"{xt(p, 'tr2:Configurations/tr2:VideoEncoder/tt:Resolution/tt:Height')}"
               f"{' PTZ' if xp(p, 'tr2:Configurations/tr2:PTZ') else ''}")


@test("X-MEDIA2-URI", "Media2 GetStreamUri and RTSP DESCRIBE", "media2", needs=("svc.media2", "media2.profiles"),
      profiles=("T",), ref="Media2 5.5.1")
def t2_uri(r):
    for p in r.d["profiles2"]:
        rep = r.call("media2", "GetStreamUri", f"<Protocol>RtspUnicast</Protocol><ProfileToken>{p['token']}</ProfileToken>")
        if not r.check(rep.ok, f"{p['token']}: {rep.why()}"):
            continue
        uri = rep.t("tr2:Uri", "")
        d = net.rtsp_describe(uri, r.ctx.user, r.ctx.password)
        r.check(d.status == 200, f"{p['token']}: DESCRIBE {uri} -> {d.error or d.status}")
        r.info(f"{p['token']}: {uri.split('@')[-1]} " + ", ".join(f"{k} {c}" for k, c, _ in d.media()))


@test("MEDIA2-5-1-1", "Media2 GetSnapshotUri", "media2", needs=("svc.media2", "media2.profiles"),
      profiles=("T",))
def t2_snap(r):
    p = r.d["profiles2"][0]
    rep = r.call("media2", "GetSnapshotUri", f"<ProfileToken>{p['token']}</ProfileToken>")
    if not rep.ok:
        r.check(False, f"{rep.why()}", else_warn=True)
        return
    s = net.snapshot(rep.t("tr2:Uri", ""), r.ctx.user, r.ctx.password)
    r.check(s.status == 200 and s.width, f"snapshot -> {s.error or s.status}")


@test("MEDIA2-2-3-5", "Media2 video encoder configuration options", "media2", needs=("svc.media2",),
      profiles=("T",))
def t2_encopts(r):
    rep = r.ok("media2", "GetVideoEncoderConfigurationOptions")
    for o in rep.x("tr2:Options"):
        r.info(f"{xt(o, 'tt:Encoding')}: {len(xp(o, 'tt:ResolutionsAvailable'))} resolutions, "
               f"profiles {o.get('ProfilesSupported') or xt(o, 'tt:ProfilesSupported')}")
