"""A small raw SOAP 1.2 client for ONVIF: WS-UsernameToken digest or HTTP
digest, every exchange kept for the trace, faults parsed into code/subcodes.

Raw on purpose: a conformance tool has to send what a library would refuse
to (bad tokens, unknown operations, odd prefixes, no auth) and see exactly
what came back."""
from __future__ import annotations

import base64
import datetime as dt
import hashlib
import os
import time
from dataclasses import dataclass, field

import httpx
from lxml import etree

NS = {
    "s": "http://www.w3.org/2003/05/soap-envelope",
    "tds": "http://www.onvif.org/ver10/device/wsdl",
    "trt": "http://www.onvif.org/ver10/media/wsdl",
    "tr2": "http://www.onvif.org/ver20/media/wsdl",
    "tptz": "http://www.onvif.org/ver20/ptz/wsdl",
    "timg": "http://www.onvif.org/ver20/imaging/wsdl",
    "tev": "http://www.onvif.org/ver10/events/wsdl",
    "tmd": "http://www.onvif.org/ver10/deviceIO/wsdl",
    "tan": "http://www.onvif.org/ver20/analytics/wsdl",
    "tt": "http://www.onvif.org/ver10/schema",
    "tns1": "http://www.onvif.org/ver10/topics",
    "wsnt": "http://docs.oasis-open.org/wsn/b-2",
    "wstop": "http://docs.oasis-open.org/wsn/t-1",
    "wsa": "http://www.w3.org/2005/08/addressing",
    "ter": "http://www.onvif.org/ver10/error",
    "wsse": "http://docs.oasis-open.org/wss/2004/01/oasis-200401-wss-wssecurity-secext-1.0.xsd",
    "wsu": "http://docs.oasis-open.org/wss/2004/01/oasis-200401-wss-wssecurity-utility-1.0.xsd",
}
# service key -> (namespace, default path under /onvif/)
SERVICES = {
    "device": (NS["tds"], "device_service"),
    "media": (NS["trt"], "media_service"),
    "media2": (NS["tr2"], "media2_service"),
    "ptz": (NS["tptz"], "ptz_service"),
    "imaging": (NS["timg"], "imaging_service"),
    "events": (NS["tev"], "events_service"),
    "deviceio": (NS["tmd"], "deviceio_service"),
    "analytics": (NS["tan"], "analytics_service"),
}
NS_TO_SERVICE = {v[0]: k for k, v in SERVICES.items()}

PW_DIGEST = ("http://docs.oasis-open.org/wss/2004/01/"
             "oasis-200401-wss-username-token-profile-1.0#PasswordDigest")
B64 = ("http://docs.oasis-open.org/wss/2004/01/"
       "oasis-200401-wss-soap-message-security-1.0#Base64Binary")


def q(prefix: str, local: str) -> str:
    return f"{{{NS[prefix]}}}{local}"


def xp(el, path: str):
    """XPath with the ONVIF prefixes; [] when el is None."""
    return [] if el is None else el.xpath(path, namespaces=NS)


def xt(el, path: str, default=None):
    r = xp(el, path)
    if not r:
        return default
    v = r[0]
    return v if isinstance(v, str) else (v.text or "").strip()


def local(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


@dataclass
class Fault:
    code: str = ""
    subcodes: list = field(default_factory=list)
    reason: str = ""

    def __str__(self):
        sc = "/".join(self.subcodes)
        return f"{self.code}{'/' + sc if sc else ''}: {self.reason}".strip()

    def has(self, *names: str) -> bool:
        """True when any subcode (or the code) ends with one of names,
        compared without prefix, e.g. has("InvalidArgVal", "NoEntity")."""
        allc = [self.code] + self.subcodes
        return any(c.rsplit(":", 1)[-1] == n for c in allc for n in names)


@dataclass
class Reply:
    service: str
    op: str
    url: str
    status: int = 0
    elapsed: float = 0.0
    text: str = ""
    root: object = None      # lxml root of the envelope
    body: object = None      # first child of s:Body
    fault: Fault | None = None
    error: str = ""          # transport / parse error
    request: str = ""

    @property
    def ok(self) -> bool:
        return not self.error and self.fault is None and self.body is not None and self.status == 200

    def why(self) -> str:
        if self.error:
            return self.error
        if self.fault:
            return f"HTTP {self.status} fault {self.fault}"
        if self.status != 200:
            return f"HTTP {self.status}"
        return "ok"

    def x(self, path):
        return xp(self.body, path)

    def t(self, path, default=None):
        return xt(self.body, path, default)


class Client:
    """auth: "wsse" (WS-UsernameToken digest, what Frigate and HA send),
    "digest" (HTTP digest only), "both", or "none"."""

    def __init__(self, host, port=80, user="", password="", timeout=10.0, auth="wsse",
                 scheme="http"):
        self.host, self.port = host, port
        self.user, self.password = user, password
        self.timeout = timeout
        self.auth = auth
        self.scheme = scheme
        self.time_offset = 0.0      # device UTC minus local UTC, seconds
        self.xaddr: dict[str, str] = {}
        self.log: list[Reply] = []
        self.http = httpx.Client(timeout=timeout, verify=False)

    # -------------------------------------------------------------- addressing
    def base(self) -> str:
        p = "" if (self.scheme, self.port) in (("http", 80), ("https", 443)) else f":{self.port}"
        return f"{self.scheme}://{self.host}{p}"

    def url(self, service: str) -> str:
        return self.xaddr.get(service) or f"{self.base()}/onvif/{SERVICES[service][1]}"

    # -------------------------------------------------------------- envelope
    def security_header(self, created: str | None = None, password: str | None = None,
                        user: str | None = None) -> str:
        pw = self.password if password is None else password
        nonce = os.urandom(16)
        if created is None:
            now = dt.datetime.now(dt.timezone.utc) + dt.timedelta(seconds=self.time_offset)
            created = now.strftime("%Y-%m-%dT%H:%M:%S.") + f"{now.microsecond // 1000:03d}Z"
        digest = base64.b64encode(hashlib.sha1(nonce + created.encode() + pw.encode()).digest()).decode()
        return (f'<wsse:Security s:mustUnderstand="1" xmlns:wsse="{NS["wsse"]}" xmlns:wsu="{NS["wsu"]}">'
                f'<wsse:UsernameToken><wsse:Username>{self.user if user is None else user}</wsse:Username>'
                f'<wsse:Password Type="{PW_DIGEST}">{digest}</wsse:Password>'
                f'<wsse:Nonce EncodingType="{B64}">{base64.b64encode(nonce).decode()}</wsse:Nonce>'
                f'<wsu:Created>{created}</wsu:Created></wsse:UsernameToken></wsse:Security>')

    def envelope(self, body: str, header: str = "") -> str:
        return (f'<?xml version="1.0" encoding="UTF-8"?>'
                f'<s:Envelope xmlns:s="{NS["s"]}" xmlns:tt="{NS["tt"]}">'
                f'<s:Header>{header}</s:Header><s:Body>{body}</s:Body></s:Envelope>')

    # -------------------------------------------------------------- calls
    def call(self, service: str, op: str, inner: str = "", *, auth: str | None = None,
             header: str | None = None, url: str | None = None, raw: str | None = None,
             timeout: float | None = None) -> Reply:
        """Send <op xmlns=service-ns>inner</op>. inner may use the tt: prefix
        and unprefixed service elements. raw replaces the whole envelope."""
        ns = SERVICES[service][0] if service in SERVICES else service
        auth = self.auth if auth is None else auth
        if raw is None:
            if header is None:
                header = self.security_header() if auth in ("wsse", "both") else ""
            raw = self.envelope(f'<{op} xmlns="{ns}">{inner}</{op}>', header)
        target = url or self.url(service if service in SERVICES else "device")
        rep = Reply(service=service, op=op, url=target, request=raw)
        hauth = (httpx.DigestAuth(self.user, self.password) if auth in ("digest", "both") else None)
        headers = {"Content-Type": f'application/soap+xml; charset=utf-8; action="{ns}/{op}"'}
        t0 = time.monotonic()
        try:
            r = self.http.post(target, content=raw.encode(), headers=headers, auth=hauth,
                               timeout=timeout or self.timeout)
            rep.status = r.status_code
            rep.text = r.text
        except httpx.HTTPError as e:
            rep.error = f"{type(e).__name__}: {e}"
        rep.elapsed = time.monotonic() - t0
        if rep.text:
            self._parse(rep)
        self.log.append(rep)
        return rep

    @staticmethod
    def _parse(rep: Reply):
        try:
            parser = etree.XMLParser(resolve_entities=False, no_network=True, huge_tree=True)
            rep.root = etree.fromstring(rep.text.encode(), parser)
        except etree.XMLSyntaxError as e:
            if not rep.error:
                rep.error = f"HTTP {rep.status}, body not XML: {e}"
            return
        body = rep.root.find(q("s", "Body"))
        if body is None:
            rep.error = rep.error or f"HTTP {rep.status}, no SOAP 1.2 Body (SOAP 1.1 envelope?)"
            return
        kids = [k for k in body if isinstance(k.tag, str)]
        rep.body = kids[0] if kids else None
        if rep.body is not None and rep.body.tag == q("s", "Fault"):
            f = Fault()
            f.code = xt(rep.body, "s:Code/s:Value", "")
            f.subcodes = [s.text.strip() for s in rep.body.xpath(".//s:Subcode/s:Value", namespaces=NS) if s.text]
            f.reason = xt(rep.body, "s:Reason/s:Text", "")
            rep.fault = f

    def close(self):
        self.http.close()
