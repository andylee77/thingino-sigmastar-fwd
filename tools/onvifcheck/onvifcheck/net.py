"""WS-Discovery probes, an RTSP DESCRIBE client and a snapshot fetcher: enough
to check that what ONVIF advertises is actually served."""
from __future__ import annotations

import base64
import hashlib
import os
import re
import socket
import struct
import time
import uuid
from dataclasses import dataclass, field
from urllib.parse import urlsplit, urlunsplit

import httpx
from lxml import etree

WSD_ADDR = ("239.255.255.250", 3702)
NS_D = "http://schemas.xmlsoap.org/ws/2005/04/discovery"
NS_A = "http://schemas.xmlsoap.org/ws/2004/08/addressing"
NS_DN = "http://www.onvif.org/ver10/network/wsdl"
NS_TDS = "http://www.onvif.org/ver10/device/wsdl"


@dataclass
class ProbeMatch:
    source: str
    epr: str = ""
    types: list = field(default_factory=list)
    scopes: list = field(default_factory=list)
    xaddrs: list = field(default_factory=list)
    metadata_version: str = ""
    raw: str = ""


def probe_message(types="dn:NetworkVideoTransmitter", scopes="", msgid=None, extra_ns=""):
    msgid = msgid or f"uuid:{uuid.uuid4()}"
    sc = f"<d:Scopes>{scopes}</d:Scopes>" if scopes else ""
    ty = f"<d:Types>{types}</d:Types>" if types else ""
    return (f'<?xml version="1.0" encoding="UTF-8"?>'
            f'<s:Envelope xmlns:s="http://www.w3.org/2003/05/soap-envelope" xmlns:a="{NS_A}" '
            f'xmlns:d="{NS_D}" xmlns:dn="{NS_DN}" xmlns:tds="{NS_TDS}" {extra_ns}>'
            f'<s:Header><a:Action s:mustUnderstand="1">{NS_D}/Probe</a:Action>'
            f'<a:MessageID>{msgid}</a:MessageID>'
            f'<a:ReplyTo><a:Address>{NS_A}/role/anonymous</a:Address></a:ReplyTo>'
            f'<a:To s:mustUnderstand="1">urn:schemas-xmlsoap-org:ws:2005:04:discovery</a:To>'
            f'</s:Header><s:Body><d:Probe>{ty}{sc}</d:Probe></s:Body></s:Envelope>')


def _parse_matches(data: bytes, src: str) -> list[ProbeMatch]:
    out = []
    try:
        root = etree.fromstring(data, etree.XMLParser(resolve_entities=False, no_network=True))
    except etree.XMLSyntaxError:
        return [ProbeMatch(source=src, raw=data.decode("utf-8", "replace"))]
    for m in root.iter(f"{{{NS_D}}}ProbeMatch"):
        pm = ProbeMatch(source=src, raw=data.decode("utf-8", "replace"))
        a = m.find(f"{{{NS_A}}}EndpointReference/{{{NS_A}}}Address")
        pm.epr = (a.text or "").strip() if a is not None else ""

        def words(tag):
            e = m.find(f"{{{NS_D}}}{tag}")
            return (e.text or "").split() if e is not None else []
        pm.types, pm.scopes, pm.xaddrs = words("Types"), words("Scopes"), words("XAddrs")
        mv = m.find(f"{{{NS_D}}}MetadataVersion")
        pm.metadata_version = (mv.text or "").strip() if mv is not None else ""
        out.append(pm)
    if not out:
        out.append(ProbeMatch(source=src, raw=data.decode("utf-8", "replace")))
    return out


def probe(target: str | None = None, timeout=3.0, message: str | None = None) -> list[ProbeMatch]:
    """Unicast to target:3702, or multicast when target is None."""
    msg = (message or probe_message()).encode()
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
    s.setsockopt(socket.IPPROTO_IP, socket.IP_MULTICAST_TTL, 4)
    s.settimeout(0.3)
    s.bind(("", 0))
    s.sendto(msg, (target, 3702) if target else WSD_ADDR)
    out, end = [], time.monotonic() + timeout
    while time.monotonic() < end:
        try:
            data, addr = s.recvfrom(65535)
        except socket.timeout:
            if target and out:
                break
            continue
        out += _parse_matches(data, addr[0])
    s.close()
    return out


# ------------------------------------------------------------------ RTSP
@dataclass
class RtspReply:
    status: int = 0
    reason: str = ""
    headers: dict = field(default_factory=dict)
    body: str = ""
    error: str = ""
    auth_scheme: str = ""

    def media(self):
        """[(kind, codec/clock, fmtp)] from the SDP."""
        out, kind, codec, fmtp = [], None, None, None
        for line in self.body.splitlines():
            if line.startswith("m="):
                if kind:
                    out.append((kind, codec, fmtp))
                kind, codec, fmtp = line[2:].split()[0], None, None
            elif line.startswith("a=rtpmap:") and kind:
                codec = codec or line.split(None, 1)[1]
            elif line.startswith("a=fmtp:") and kind:
                fmtp = fmtp or line.split(None, 1)[1]
        if kind:
            out.append((kind, codec, fmtp))
        return out


def _rtsp_send(sock, req: str) -> RtspReply:
    sock.sendall(req.encode())
    buf = b""
    while b"\r\n\r\n" not in buf:
        chunk = sock.recv(4096)
        if not chunk:
            break
        buf += chunk
    head, _, rest = buf.partition(b"\r\n\r\n")
    lines = head.decode("utf-8", "replace").split("\r\n")
    rep = RtspReply()
    m = re.match(r"RTSP/1\.0 (\d+) ?(.*)", lines[0] if lines else "")
    if not m:
        rep.error = f"bad status line: {lines[:1]}"
        return rep
    rep.status, rep.reason = int(m.group(1)), m.group(2)
    for ln in lines[1:]:
        k, _, v = ln.partition(":")
        rep.headers.setdefault(k.strip().lower(), []).append(v.strip())
    n = int(rep.headers.get("content-length", ["0"])[0] or 0)
    while len(rest) < n:
        chunk = sock.recv(4096)
        if not chunk:
            break
        rest += chunk
    rep.body = rest[:n].decode("utf-8", "replace")
    return rep


def _digest(user, pw, method, uri, chal: str) -> str:
    p = dict(re.findall(r'(\w+)="?([^",]*)"?', chal))
    realm, nonce = p.get("realm", ""), p.get("nonce", "")
    ha1 = hashlib.md5(f"{user}:{realm}:{pw}".encode()).hexdigest()
    ha2 = hashlib.md5(f"{method}:{uri}".encode()).hexdigest()
    if "auth" in p.get("qop", ""):
        nc, cn = "00000001", os.urandom(8).hex()
        resp = hashlib.md5(f"{ha1}:{nonce}:{nc}:{cn}:auth:{ha2}".encode()).hexdigest()
        return (f'Digest username="{user}", realm="{realm}", nonce="{nonce}", uri="{uri}", '
                f'response="{resp}", qop=auth, nc={nc}, cnonce="{cn}"')
    resp = hashlib.md5(f"{ha1}:{nonce}:{ha2}".encode()).hexdigest()
    return f'Digest username="{user}", realm="{realm}", nonce="{nonce}", uri="{uri}", response="{resp}"'


def rtsp_describe(uri: str, user="", pw="", timeout=6.0) -> RtspReply:
    """DESCRIBE with the URI's own credentials, else user/pw (Digest or
    Basic as the server asks). No SETUP/PLAY: nothing is streamed."""
    u = urlsplit(uri)
    if u.username:
        user, pw = u.username, u.password or ""
    host, port = u.hostname, u.port or 554
    clean = urlunsplit((u.scheme, f"{host}:{u.port}" if u.port else host, u.path, u.query, ""))
    try:
        sock = socket.create_connection((host, port), timeout=timeout)
    except OSError as e:
        return RtspReply(error=f"connect {host}:{port}: {e}")
    sock.settimeout(timeout)
    try:
        base = f"DESCRIBE {clean} RTSP/1.0\r\nAccept: application/sdp\r\nUser-Agent: onvifcheck\r\n"
        rep = _rtsp_send(sock, base + "CSeq: 1\r\n\r\n")
        if rep.status == 401:
            chals = rep.headers.get("www-authenticate", [])
            dig = next((c for c in chals if c.lower().startswith("digest")), None)
            if dig:
                auth = _digest(user, pw, "DESCRIBE", clean, dig)
                scheme = "Digest"
            else:
                auth = "Basic " + base64.b64encode(f"{user}:{pw}".encode()).decode()
                scheme = "Basic"
            rep = _rtsp_send(sock, base + f"CSeq: 2\r\nAuthorization: {auth}\r\n\r\n")
            rep.auth_scheme = scheme
        return rep
    except OSError as e:
        return RtspReply(error=f"{type(e).__name__}: {e}")
    finally:
        sock.close()


# ------------------------------------------------------------------ snapshot
@dataclass
class Snapshot:
    status: int = 0
    ctype: str = ""
    size: int = 0
    width: int = 0
    height: int = 0
    error: str = ""
    data: bytes = b""
    auth: str = ""


def jpeg_size(b: bytes):
    if not b.startswith(b"\xff\xd8"):
        return None
    i = 2
    while i + 9 < len(b):
        if b[i] != 0xFF:
            i += 1
            continue
        marker = b[i + 1]
        if marker in (0xC0, 0xC1, 0xC2, 0xC3, 0xC5, 0xC6, 0xC7, 0xC9, 0xCA, 0xCB, 0xCD, 0xCE, 0xCF):
            h, w = struct.unpack(">HH", b[i + 5:i + 9])
            return w, h
        if marker in (0xD8, 0x01) or 0xD0 <= marker <= 0xD7:
            i += 2
            continue
        seg = struct.unpack(">H", b[i + 2:i + 4])[0]
        i += 2 + seg
    return None


def snapshot(uri: str, user="", pw="", timeout=10.0) -> Snapshot:
    """GET as HA/Frigate do: try no auth, then Digest, then Basic."""
    s = Snapshot()
    with httpx.Client(timeout=timeout, verify=False, follow_redirects=True) as h:
        for name, auth in (("none", None), ("digest", httpx.DigestAuth(user, pw)),
                           ("basic", httpx.BasicAuth(user, pw))):
            try:
                r = h.get(uri, auth=auth)
            except httpx.HTTPError as e:
                s.error = f"{type(e).__name__}: {e}"
                return s
            s.status, s.ctype = r.status_code, r.headers.get("content-type", "")
            if r.status_code == 200:
                s.data, s.size, s.auth = r.content, len(r.content), name
                wh = jpeg_size(r.content)
                if wh:
                    s.width, s.height = wh
                return s
            if r.status_code != 401:
                return s
    return s
