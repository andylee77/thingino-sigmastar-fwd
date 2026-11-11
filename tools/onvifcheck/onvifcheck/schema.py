"""Two views of every response body:

1. The spec view: XSD validation against the ONVIF schemas of a pinned
   release of github.com/onvif/specs (fetched once into a cache).
2. The client view: the body parsed by zeep the way onvif-zeep-async (Frigate,
   Home Assistant) parses it, non-strict, with that library's own bundled
   WSDLs. Non-strict zeep drops an element it meets out of order instead of
   failing, so a leaf present in the XML but None in zeep's object is a field
   the client silently never sees (the 0008 "zoom spaces in schema order"
   class of bug)."""
from __future__ import annotations

import os
import pathlib
import sys

import logging

import httpx
from lxml import etree

logging.getLogger("httpx").setLevel(logging.WARNING)

from .soap import NS, local

SPEC_TAG = "26.06"
SPEC_BASE = "https://raw.githubusercontent.com/onvif/specs/{tag}/"
SPEC_FILES = [
    "wsdl/ver10/schema/onvif.xsd",
    "wsdl/ver10/schema/common.xsd",
    "wsdl/ver10/schema/metadatastream.xsd",
    "wsdl/ver20/analytics/humanbody.xsd",
    "wsdl/ver20/analytics/humanface.xsd",
    "wsdl/ver10/device/wsdl/devicemgmt.wsdl",
    "wsdl/ver10/media/wsdl/media.wsdl",
    "wsdl/ver20/media/wsdl/media.wsdl",
    "wsdl/ver20/ptz/wsdl/ptz.wsdl",
    "wsdl/ver20/imaging/wsdl/imaging.wsdl",
    "wsdl/ver10/events/wsdl/event.wsdl",
    "wsdl/ver10/deviceio.wsdl",
]
SOAP12_URL = "https://www.w3.org/2003/05/soap-envelope/"
# response namespace -> schema source in the spec set
SPEC_BY_NS = {
    NS["tds"]: "wsdl/ver10/device/wsdl/devicemgmt.wsdl",
    NS["trt"]: "wsdl/ver10/media/wsdl/media.wsdl",
    NS["tr2"]: "wsdl/ver20/media/wsdl/media.wsdl",
    NS["tptz"]: "wsdl/ver20/ptz/wsdl/ptz.wsdl",
    NS["timg"]: "wsdl/ver20/imaging/wsdl/imaging.wsdl",
    NS["tev"]: "wsdl/ver10/events/wsdl/event.wsdl",
    NS["tmd"]: "wsdl/ver10/deviceio.wsdl",
    NS["wsnt"]: "@b-2.xsd",
}
# response namespace -> WSDL bundled with onvif-zeep-async
ZEEP_BY_NS = {
    NS["tds"]: "devicemgmt.wsdl",
    NS["trt"]: "media.wsdl",
    NS["tptz"]: "ptz.wsdl",
    NS["timg"]: "imaging.wsdl",
    NS["tev"]: "events.wsdl",
    NS["tmd"]: "deviceio.wsdl",
}
XS = "http://www.w3.org/2001/XMLSchema"


def cache_dir() -> pathlib.Path:
    base = os.environ.get("LOCALAPPDATA") or os.path.expanduser("~/.cache")
    return pathlib.Path(base) / "onvifcheck" / "schemas" / SPEC_TAG


def onvif_pkg_wsdl() -> pathlib.Path | None:
    try:
        import onvif  # onvif-zeep-async
    except ImportError:
        return None
    return pathlib.Path(onvif.__file__).parent / "wsdl"


def fetch_spec(force=False, quiet=False) -> pathlib.Path:
    d = cache_dir()
    with httpx.Client(timeout=30, follow_redirects=True) as h:
        for rel in SPEC_FILES:
            p = d / rel
            if p.exists() and not force:
                continue
            p.parent.mkdir(parents=True, exist_ok=True)
            r = h.get(SPEC_BASE.format(tag=SPEC_TAG) + rel)
            r.raise_for_status()
            p.write_bytes(r.content)
            if not quiet:
                print(f"fetched {rel}", file=sys.stderr)
        p = d / "ext" / "soap-envelope.xsd"
        if not p.exists() or force:
            p.parent.mkdir(parents=True, exist_ok=True)
            r = h.get(SOAP12_URL)
            r.raise_for_status()
            p.write_bytes(r.content)
    return d


class _Resolver(etree.Resolver):
    """Map the schemas' absolute imports onto local copies."""

    def __init__(self, spec_dir: pathlib.Path, pkg: pathlib.Path):
        super().__init__()
        self.map = {
            "soap-envelope": spec_dir / "ext" / "soap-envelope.xsd",
            "b-2.xsd": pkg / "b-2.xsd", "t-1.xsd": pkg / "t-1.xsd",
            "ws-addr.xsd": pkg / "ws-addr.xsd", "bf-2.xsd": pkg / "bf-2.xsd",
            "r-2.xsd": pkg / "r-2.xsd", "xml.xsd": pkg / "xml.xsd",
            "xmlmime": pkg / "xmlmime", "include": pkg / "include",
        }

    def resolve(self, url, pubid, context):
        if url.startswith(("http://", "https://")):
            key = url.rstrip("/").rsplit("/", 1)[-1]
            p = self.map.get(key)
            if p and p.exists():
                return self.resolve_filename(str(p), context)
            return None
        if url.endswith(".xsd"):
            path = url[8:] if url.startswith("file:///") else url
            try:
                text = pathlib.Path(path).read_bytes()
            except OSError:
                return None
            return self.resolve_string(deterministic(text), context, base_url=url)
        return None


def deterministic(text: bytes) -> bytes:
    """libxml2 enforces Unique Particle Attribution; several ONVIF types end a
    sequence of optional tt: elements with <xs:any namespace="##any"> or
    "##targetNamespace", which it rejects as non-deterministic. Narrow those
    wildcards to ##other: vendor extensions in other namespaces still
    validate, unknown tt: elements no longer do (they are not in the spec)."""
    return (text.replace(b'namespace="##targetNamespace"', b'namespace="##other"')
                .replace(b'namespace="##any"', b'namespace="##other"'))


class SpecValidator:
    def __init__(self, auto_fetch=True):
        self.ok = False
        self.why = ""
        self.schemas: dict[str, etree.XMLSchema] = {}
        self.errors: dict[str, str] = {}
        pkg = onvif_pkg_wsdl()
        if pkg is None:
            self.why = "onvif-zeep-async not installed (its OASIS/W3C schemas are reused)"
            return
        d = cache_dir()
        if not all((d / f).exists() for f in SPEC_FILES) and auto_fetch:
            try:
                fetch_spec(quiet=True)
            except Exception as e:  # noqa: BLE001
                self.why = f"could not fetch ONVIF {SPEC_TAG} schemas: {e}"
                return
        self.dir, self.pkg = self._patched(d, pkg), pkg
        self.parser = etree.XMLParser(no_network=True, huge_tree=True)
        self.parser.resolvers.add(_Resolver(d, pkg))
        self.ok = True

    @staticmethod
    def _patched(d: pathlib.Path, pkg: pathlib.Path) -> pathlib.Path:
        """A copy of the spec set that libxml2 compiles offline: wildcards made
        deterministic, absolute imports pointed at local files."""
        out = d / "patched"
        stamp = out / ".stamp"
        if stamp.exists():
            return out
        res = _Resolver(d, pkg)
        for rel in SPEC_FILES + ["ext/soap-envelope.xsd"]:
            text = deterministic((d / rel).read_bytes())
            for key, p in res.map.items():
                for scheme in (b"http://", b"https://"):
                    import re
                    text = re.sub(rb'(schemaLocation|location)="' + scheme + rb'[^"]*/' + re.escape(key.encode()) + rb'/?"',
                                  lambda m: m.group(1) + b'="' + p.as_uri().encode() + b'"', text)
            (out / rel).parent.mkdir(parents=True, exist_ok=True)
            (out / rel).write_bytes(text)
        stamp.write_text(SPEC_TAG)
        return out

    def _schema(self, src: str):
        if src in self.schemas or src in self.errors:
            return self.schemas.get(src)
        try:
            if src.startswith("@"):
                path = self.pkg / src[1:]
                doc = etree.parse(str(path), self.parser)
                sch = etree.XMLSchema(doc)
            else:
                path = self.dir / src
                wsdl = etree.fromstring(deterministic(path.read_bytes()), self.parser,
                                        base_url=str(path))
                s = wsdl.find(f".//{{{XS}}}schema")
                nsmap = {k: v for k, v in {**wsdl.nsmap, **s.nsmap}.items() if k}
                new = etree.Element(f"{{{XS}}}schema", nsmap=nsmap, attrib=dict(s.attrib))
                for ch in s:
                    new.append(ch)
                text = etree.tostring(new)
                doc = etree.fromstring(text, self.parser, base_url=str(path))
                sch = etree.XMLSchema(doc)
            self.schemas[src] = sch
            return sch
        except (etree.XMLSchemaParseError, etree.XMLSyntaxError, OSError) as e:
            self.errors[src] = str(e)
            return None

    def validate(self, body) -> list[str] | None:
        """[] valid, [errors...] invalid, None no schema for this element."""
        if not self.ok or body is None:
            return None
        ns = body.tag[1:].split("}", 1)[0]
        src = SPEC_BY_NS.get(ns)
        if not src:
            return None
        sch = self._schema(src)
        if sch is None:
            return None
        if sch.validate(body):
            return []
        out = []
        for e in sch.error_log:
            msg = e.message.replace("{http://www.onvif.org/ver10/schema}", "tt:")
            for p, u in NS.items():
                msg = msg.replace("{" + u + "}", p + ":")
            out.append(msg)
        return out


# ------------------------------------------------------------- client view
class ZeepView:
    def __init__(self):
        self.ok = False
        self.clients = {}
        self.why = ""
        try:
            import zeep  # noqa: F401
            from zeep.helpers import serialize_object  # noqa: F401
        except ImportError:
            self.why = "zeep not installed"
            return
        self.pkg = onvif_pkg_wsdl()
        if self.pkg is None:
            self.why = "onvif-zeep-async not installed"
            return
        self.ok = True

    def _client(self, wsdl):
        if wsdl not in self.clients:
            from zeep import Client, Settings
            s = Settings(strict=False, xml_huge_tree=True)
            try:
                self.clients[wsdl] = Client(str(self.pkg / wsdl), settings=s)
            except Exception as e:  # noqa: BLE001
                self.clients[wsdl] = None
                self.why = f"{wsdl}: {e}"
        return self.clients[wsdl]

    def parse(self, body):
        """-> (zeep object or None, error string or None)"""
        if not self.ok or body is None:
            return None, "no zeep"
        ns = body.tag[1:].split("}", 1)[0]
        wsdl = ZEEP_BY_NS.get(ns)
        if not wsdl:
            return None, "no bundled WSDL for this namespace"
        c = self._client(wsdl)
        if c is None:
            return None, self.why
        try:
            el = c.get_element(body.tag)
        except Exception as e:  # noqa: BLE001
            return None, f"zeep does not know {local(body.tag)}: {e}"
        try:
            return el.parse(body, c.wsdl.types), None
        except Exception as e:  # noqa: BLE001
            return None, f"zeep parse error: {type(e).__name__}: {e}"

    def lost(self, body) -> list[str] | None:
        """Elements zeep could not place: non-strict zeep parks an element it
        meets out of schema order (or does not know) in _raw_elements, and
        the field it belonged to reads None. Each entry is
        'path: skipped-element' (and everything after it in that sequence is
        lost too). None when this response cannot be checked."""
        obj, err = self.parse(body)
        if err:
            if err.startswith(("no ", "zeep does not know")):
                return None  # the client library has no such operation
            return [err[:200]]
        from zeep.helpers import serialize_object
        out = []
        _raw(serialize_object(obj, dict), "", out)
        return out


def _raw(o, path, out):
    if isinstance(o, dict):
        for k, v in o.items():
            if k == "_raw_elements" and v:
                for e in v:
                    tag = getattr(e, "tag", None)
                    if isinstance(tag, str):
                        ns = tag[1:].split("}", 1)[0]
                        pfx = next((p for p, u in NS.items() if u == ns), "?")
                        out.append(f"{path or '(top)'}: {pfx}:{local(tag)}")
            elif isinstance(v, (dict, list)):
                _raw(v, path if k == "_value_1" else (f"{path}/{k}" if path else k), out)
    elif isinstance(o, list):
        for v in o:
            _raw(v, path, out)

