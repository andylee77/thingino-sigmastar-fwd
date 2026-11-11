"""onvifcheck command line."""
from __future__ import annotations

import argparse
import ipaddress
import json
import os
import pathlib
import sys

from . import report
from .core import CATS, CONFIG, MOVE, PRESET, READ, SESSION, TESTS, Context

# importing the suites registers their tests
from . import t_device, t_media, t_ptz, t_imaging, t_events, t_deviceio, t_clients  # noqa: F401,E401

def fleet_lookup(path, name):
    """-> (ip, mac) from a fleet file, by unit name or the tail of its MAC.

    The file is JSON: {"units": {"<name>": {"mac": "aa:bb:...", "last_ip": "192.0.2.10"}}}.
    """
    if not path:
        return None, None
    try:
        units = json.loads(pathlib.Path(path).expanduser().read_text())["units"]
    except (OSError, KeyError, ValueError):
        return None, None
    key = name.lower()
    for n, u in units.items():
        mac = (u.get("mac") or "").lower()
        if n.lower() == key or mac.replace(":", "").endswith(key.replace(":", "")):
            return u.get("last_ip"), mac
    return None, None


def recorded_argv(argv):
    """The command line as written into the results, with the password masked."""
    out, mask = [], False
    for arg in argv:
        if mask:
            out.append("***")
            mask = False
        elif arg in ("-p", "--password"):
            out.append(arg)
            mask = True
        elif arg.startswith("--password="):
            out.append("--password=***")
        elif arg.startswith("-p") and len(arg) > 2:
            out.append("-p***")
        else:
            out.append(arg)
    return out


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    ap = argparse.ArgumentParser(prog="onvifcheck", description=__doc__)
    ap.add_argument("target", nargs="?", help="camera IP or host name, or a unit name from the --fleet file")
    ap.add_argument("--port", type=int, default=80)
    ap.add_argument("-u", "--user", default=os.environ.get("ONVIF_USER"),
                    help="ONVIF user (default: $ONVIF_USER)")
    ap.add_argument("-p", "--password", default=os.environ.get("ONVIF_PASS"),
                    help="ONVIF password (default: $ONVIF_PASS; prefer the variable, the shell keeps history)")
    ap.add_argument("--fleet", default=os.environ.get("ONVIFCHECK_FLEET"),
                    help="JSON file mapping unit names to IP and MAC (default: $ONVIFCHECK_FLEET)")
    ap.add_argument("--auth", choices=("wsse", "digest", "both"), default="wsse",
                    help="auth for ordinary calls (default wsse, as Frigate and HA send)")
    ap.add_argument("--mac", help="expected MAC (or its tail); required for config/move/preset tests")
    ap.add_argument("--suite", help="comma list: device,discovery,media,media2,ptz,imaging,events,deviceio,clients")
    ap.add_argument("--only", help="comma list of test-id globs, e.g. 'PTZ-*,X-FRIGATE-*'")
    ap.add_argument("--skip", help="comma list of test-id globs to skip")
    ap.add_argument("--client", help="only tests a client relies on: frigate,ha,go2rtc")
    ap.add_argument("--allow-move", action="store_true", help="run PTZ/focus motion tests (moves the head!)")
    ap.add_argument("--allow-config", action="store_true",
                    help="run Set* tests (imaging, relays); each restores what it changed")
    ap.add_argument("--allow-preset-write", action="store_true",
                    help="run SetPreset/RemovePreset (a board may hold positions it does not list)")
    ap.add_argument("--no-session", action="store_true", help="skip event subscriptions")
    ap.add_argument("--preset", help="preset token for the GotoPreset test (default: home, else the first)")
    ap.add_argument("--relay", help="relay token for the relay toggle test (default: all)")
    ap.add_argument("--return-preset", default="home",
                    help="Frigate's autotracking return_preset to look for (default home)")
    ap.add_argument("--no-schema", action="store_true", help="skip XSD validation and the zeep view")
    ap.add_argument("--strict-schema", action="store_true", help="XSD errors fail a test (default: warn)")
    ap.add_argument("--timeout", type=float, default=10.0)
    ap.add_argument("-o", "--out", help="write results.json/.csv, summary.md and trace/ here")
    ap.add_argument("-v", "--verbose", action="store_true", help="print every test's details")
    ap.add_argument("--list", action="store_true", help="list the tests and exit")
    ap.add_argument("--discover", action="store_true", help="multicast WS-Discovery probe and exit")
    ap.add_argument("--fetch-schemas", action="store_true", help="download the ONVIF schemas and exit")
    a = ap.parse_args(argv)

    if a.list:
        for t in TESTS:
            print(f"{t.id:22s} {t.service:9s} {t.cat:8s} {','.join(t.clients):18s} {t.title}")
        print(f"{len(TESTS)} tests")
        return 0
    if a.fetch_schemas:
        from .schema import fetch_spec
        print(fetch_spec(force=True))
        return 0
    if a.discover:
        from . import net
        for m in net.probe(None, timeout=4):
            print(f"{m.source:15s} {' '.join(m.xaddrs)}\n    {' '.join(m.types)}\n    "
                  + " ".join(s.replace("onvif://www.onvif.org/", "") for s in m.scopes))
        return 0
    if not a.target:
        ap.error("a target is needed (there is no default camera: motion tests move a real head)")
    if not a.user or not a.password:
        ap.error("credentials are needed: -u and -p, or ONVIF_USER and ONVIF_PASS in the environment")

    host, mac, name = a.target, a.mac, a.target
    try:
        ipaddress.ip_address(a.target)
    except ValueError:
        ip, fmac = fleet_lookup(a.fleet, a.target)
        if ip:
            host, mac = ip, mac or fmac
    allow = {READ} | (set() if a.no_session else {SESSION})
    allow |= {MOVE} if a.allow_move else set()
    allow |= {CONFIG} if a.allow_config else set()
    allow |= {PRESET} if a.allow_preset_write else set()

    ctx = Context(host, a.port, a.user, a.password, auth=a.auth, timeout=a.timeout, allow=allow,
                  expect_mac=mac, name=name, validate=not a.no_schema, strict_schema=a.strict_schema, args=a)
    print(f"onvifcheck {name} ({host}:{a.port})", flush=True)
    ctx.discover()
    print(report.features_text(ctx), flush=True)
    if (MOVE in allow or CONFIG in allow or PRESET in allow) and ctx.mac_ok is not True:
        print("!! motion/config tests will be skipped: "
              + ("MAC mismatch" if ctx.mac_ok is False else "no --mac (or fleet entry) to check the MAC against"))
    if ctx.validator is not None and not ctx.validator.ok:
        print(f"note: no XSD validation ({ctx.validator.why})")
    print()
    tests = ctx.select(only=a.only.split(",") if a.only else None,
                       skip=a.skip.split(",") if a.skip else None,
                       suites=set(a.suite.split(",")) if a.suite else None,
                       clients=a.client.split(",") if a.client else None)
    results = ctx.run(tests, on_result=lambda r: print(report.line(r, a.verbose), flush=True))
    print("\n" + report.summary(results))
    if a.out:
        out = pathlib.Path(a.out)
        report.write(out, ctx, results, ["onvifcheck"] + recorded_argv(argv))
        print(f"wrote {out}")
    ctx.client.close()
    return 1 if any(r.status in ("FAIL", "ERROR") for r in results) else 0


if __name__ == "__main__":
    sys.exit(main())
