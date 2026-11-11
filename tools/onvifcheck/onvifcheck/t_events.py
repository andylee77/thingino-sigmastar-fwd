"""Event service tests: properties, PullPoint (what HA uses when it cannot get
webhooks), base notification Subscribe with a local consumer."""
from __future__ import annotations

import http.server
import socket
import threading
import time

from .core import SESSION, test
from .soap import NS, xp, xt

STD_TOPICS = {
    "tns1:VideoSource/MotionAlarm": "motion (HA binary_sensor)",
    "tns1:RuleEngine/CellMotionDetector/Motion": "cell motion (HA binary_sensor)",
    "tns1:VideoSource/ImageTooBlurry": "tamper",
    "tns1:VideoSource/GlobalSceneChange": "tamper",
    "tns1:Device/Trigger/DigitalInput": "digital input",
    "tns1:Device/Trigger/Relay": "relay state",
    "tns1:PTZController/PTZPresets": "PTZ preset reached",
}


def _topics(el, prefix=""):
    """Leaf topic paths from a TopicSet (elements marked wstop:topic="true")."""
    out = []
    for ch in el:
        if not isinstance(ch.tag, str):
            continue
        name = ch.tag.rsplit("}", 1)[-1]
        if name == "MessageDescription":
            continue
        path = f"{prefix}/{name}" if prefix else name
        if ch.get(f"{{{NS['wstop']}}}topic") == "true":
            out.append(path)
        out += _topics(ch, path)
    return out


@test("EVENT-5-1-1", "Events GetServiceCapabilities", "events", needs=("svc.events",), clients=("ha",),
      profiles=("S", "T", "M", "G"))
def t_caps(r):
    rep = r.ok("events", "GetServiceCapabilities")
    cap = rep.x("tev:Capabilities")
    r.check(cap, "no Capabilities")
    if cap:
        r.info(" ".join(f"{k}={v}" for k, v in cap[0].attrib.items()))
        r.check(cap[0].get("WSPullPointSupport") in ("true", "1"),
                "WSPullPointSupport is not true (PullPoint is mandatory for S/T/M/G)")


@test("EVENT-1-1-2", "GetEventProperties: topic set", "events", needs=("svc.events",), clients=("ha",),
      profiles=("S", "T", "M", "G"))
def t_props(r):
    rep = r.ok("events", "GetEventProperties")
    ts = rep.x("wstop:TopicSet")
    r.check(ts, "no TopicSet")
    topics = _topics(ts[0]) if ts else []
    r.d["topics"] = topics
    std = [f"{t} ({w})" for t, w in STD_TOPICS.items() if t.split(":", 1)[1] in topics]
    r.info(f"{len(topics)} topics: " + ", ".join(topics))
    r.info("standard: " + (", ".join(std) or "none"))
    r.check(rep.t("wsnt:FixedTopicSet") is not None, "no FixedTopicSet", else_warn=True)
    dialects = rep.x("wsnt:TopicExpressionDialect/text()")
    r.check(any("ConcreteSet" in d for d in dialects), f"ConcreteSet dialect missing ({dialects})", else_warn=True)


def _create(r, inner="<InitialTerminationTime>PT60S</InitialTerminationTime>"):
    rep = r.call("events", "CreatePullPointSubscription", inner)
    if not rep.ok:
        r.fail(f"CreatePullPointSubscription: {rep.why()}")
    addr = rep.t("tev:SubscriptionReference/wsa:Address")
    r.check(addr, "no SubscriptionReference/Address")
    r.check(rep.t("wsnt:CurrentTime") and rep.t("wsnt:TerminationTime"), "no CurrentTime/TerminationTime")
    return addr, rep


def _sub_call(r, addr, ns_key, op, inner=""):
    hdr = (r.c.security_header() + f'<wsa:Action xmlns:wsa="{NS["wsa"]}">{NS[ns_key]}/{op}</wsa:Action>'
           f'<wsa:To xmlns:wsa="{NS["wsa"]}">{addr}</wsa:To>')
    return r.call(NS[ns_key] if ns_key != "tev" else "events", op, inner, header=hdr,
                  url=addr if "://" in addr else None)


def _pull(r, addr, timeout="PT2S", limit=20):
    return _sub_call(r, addr, "tev", "PullMessages", f"<Timeout>{timeout}</Timeout><MessageLimit>{limit}</MessageLimit>")


def _msgs(rep):
    out = []
    for m in rep.x("wsnt:NotificationMessage"):
        topic = xt(m, "wsnt:Topic", "")
        op = xt(m, ".//tt:Message/@PropertyOperation", "")
        data = ", ".join(f"{i.get('Name')}={i.get('Value')}" for i in xp(m, ".//tt:Data/tt:SimpleItem"))
        out.append((topic, op, data))
    return out


@test("EVENT-3-1-15", "PullPoint: create, pull initial property states, sync point, renew, unsubscribe",
      "events", cat=SESSION, needs=("svc.events",), clients=("ha",), profiles=("S", "T", "M", "G"),
      ref="EVENT-3-1-9/12/15/25/36, Core 9.1")
def t_pullpoint(r):
    addr, _ = _create(r)
    try:
        rep = _pull(r, addr)
        if not r.check(rep.ok, f"PullMessages: {rep.why()}"):
            return
        r.check(rep.t("tev:CurrentTime") and rep.t("tev:TerminationTime"), "PullMessagesResponse lacks times")
        first = _msgs(rep)
        r.info(f"first pull: {len(first)} messages " + "; ".join(f"{t} {o} {d}" for t, o, d in first[:8]))
        props = [m for m in first if m[1] == "Initialized"]
        r.check(props or not r.d.get("topics"),
                "no Initialized property messages after subscribing (Core 9.1.2: a new subscription gets "
                "the current state of every property; HA shows motion as unknown until the first change)",
                else_warn=True)
        sp = _sub_call(r, addr, "tev", "SetSynchronizationPoint")
        r.check(sp.ok, f"SetSynchronizationPoint: {sp.why()}")
        if sp.ok:
            again = _msgs(_pull(r, addr))
            r.info(f"after SetSynchronizationPoint: {len(again)} messages")
            r.check(len(again) or not props, "SetSynchronizationPoint did not resend the property states",
                    else_warn=True)
        rn = _sub_call(r, addr, "wsnt", "Renew", "<TerminationTime>PT120S</TerminationTime>")
        r.check(rn.ok, f"Renew: {rn.why()}")
    finally:
        un = _sub_call(r, addr, "wsnt", "Unsubscribe")
        r.check(un.ok, f"Unsubscribe: {un.why()}")
    after = _pull(r, addr)
    r.check(not after.ok, "PullMessages still works on an unsubscribed pull point (EVENT-3-1-19)", else_warn=True)


@test("EVENT-3-1-32", "PullMessages waits for its Timeout when nothing happens", "events", cat=SESSION,
      needs=("svc.events",), clients=("ha",), profiles=("S", "T"), ref="EVENT-3-1-32; HA long-polls")
def t_longpoll(r):
    addr, _ = _create(r)
    try:
        _pull(r, addr, "PT1S")  # drain the initial states
        t0 = time.monotonic()
        rep = _pull(r, addr, "PT5S", 10)
        dt = time.monotonic() - t0
        r.check(rep.ok, f"PullMessages: {rep.why()}")
        n = len(_msgs(rep))
        if n == 0:
            r.check(dt > 3.5, f"an empty PullMessages returned after {dt:.1f} s, not ~5 s (HA would busy-poll)",
                    else_warn=True)
        r.info(f"PT5S pull returned {n} messages after {dt:.1f} s")
    finally:
        _sub_call(r, addr, "wsnt", "Unsubscribe")


def _local_ip_towards(host):
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect((host, 80))
        return s.getsockname()[0]
    finally:
        s.close()


@test("EVENT-2-1-9", "Base notification: Subscribe, receive Notify, Unsubscribe", "events", cat=SESSION,
      needs=("svc.events",), clients=("ha",), profiles=("S", "T"),
      ref="EVENT-2-1-9/17/28; HA prefers this (webhook) when the camera can reach it")
def t_subscribe(r):
    got = []

    class H(http.server.BaseHTTPRequestHandler):
        def do_POST(self):  # noqa: N802
            n = int(self.headers.get("Content-Length", 0))
            got.append(self.rfile.read(n).decode("utf-8", "replace"))
            self.send_response(200)
            self.send_header("Content-Length", "0")
            self.end_headers()

        def log_message(self, *a):
            pass
    ip = _local_ip_towards(r.ctx.host)
    srv = http.server.ThreadingHTTPServer((ip, 0), H)
    th = threading.Thread(target=srv.serve_forever, daemon=True)
    th.start()
    consumer = f"http://{ip}:{srv.server_address[1]}/onvifcheck"
    addr = None
    try:
        # wsnt:Subscribe, sent to the event service's address, with the
        # WS-Addressing headers onvif-zeep-async adds (HA's path)
        ev = r.c.url("events")
        hdr = (r.c.security_header() + f'<wsa:Action xmlns:wsa="{NS["wsa"]}">'
               "http://docs.oasis-open.org/wsn/bw-2/NotificationProducer/SubscribeRequest</wsa:Action>"
               f'<wsa:MessageID xmlns:wsa="{NS["wsa"]}">urn:uuid:{__import__("uuid").uuid4()}</wsa:MessageID>'
               f'<wsa:To xmlns:wsa="{NS["wsa"]}">{ev}</wsa:To>')
        rep = r.call(NS["wsnt"], "Subscribe",
                     f'<ConsumerReference><Address xmlns="{NS["wsa"]}">{consumer}</Address></ConsumerReference>'
                     '<InitialTerminationTime>PT60S</InitialTerminationTime>', url=ev, header=hdr)
        if not r.check(rep.ok, f"Subscribe: {rep.why()}"):
            return
        addr = rep.t("wsnt:SubscriptionReference/wsa:Address")
        r.check(addr, "no SubscriptionReference")
        t0 = time.monotonic()
        while not got and time.monotonic() - t0 < 8:
            time.sleep(0.2)
        r.check(got, f"no Notify reached {consumer} in 8 s (no initial states sent, or a firewall on this PC)",
                else_warn=True)
        if got:
            r.info(f"{len(got)} Notify posts, first {len(got[0])} B")
    finally:
        if addr:
            un = _sub_call(r, addr, "wsnt", "Unsubscribe")
            r.check(un.ok, f"Unsubscribe: {un.why()}", else_warn=True)
        srv.shutdown()
