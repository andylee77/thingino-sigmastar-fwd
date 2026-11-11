"""Console lines, and JSON / CSV / Markdown / trace files."""
from __future__ import annotations

import csv
import datetime as dt
import json
import pathlib
import sys

from .core import ERROR, FAIL, NA, PASS, SKIP, WARN

COLOR = {PASS: "\033[32m", WARN: "\033[33m", FAIL: "\033[31m", ERROR: "\033[35m", NA: "\033[90m",
         SKIP: "\033[90m"}


def use_color():
    return sys.stdout.isatty()


def line(r, verbose=False):
    t = r.test
    c, z = (COLOR.get(r.status, ""), "\033[0m") if use_color() else ("", "")
    head = f"{c}{r.status:5s}{z} {t.id:20s} {t.title}"
    if r.duration:
        head += f"  ({r.duration * 1000:.0f} ms)"
    out = [head]
    msgs = r.messages if (verbose or r.status not in (PASS,)) else []
    if verbose or r.status != PASS:
        msgs = r.messages
    for m in msgs:
        out.append(f"      {m}")
    if r.schema:
        out.append(f"      schema ({len(r.schema)}): " + r.schema[0][:300])
        for s in r.schema[1:4 if not verbose else None]:
            out.append(f"        {s[:300]}")
    if r.lost:
        out.append("      zeep skips (Frigate/HA read None there, and lose what follows): "
                   + "; ".join(r.lost[:6]))
    return "\n".join(out)


def summary(results):
    n = {}
    for r in results:
        n[r.status] = n.get(r.status, 0) + 1
    return " ".join(f"{k} {n[k]}" for k in (PASS, WARN, FAIL, ERROR, NA, SKIP) if k in n)


def features_text(ctx):
    d, f = ctx.data, ctx.features
    info = d.get("info", {})
    lines = [f"{info.get('Manufacturer', '?')} {info.get('Model', '?')} fw {info.get('FirmwareVersion', '?')} "
             f"MAC {', '.join(d.get('macs', [])) or '?'}"
             + ("" if ctx.mac_ok is None else (" (matches)" if ctx.mac_ok else " (MISMATCH)"))]
    svcs = [k[4:] for k, v in f.items() if k.startswith("svc.") and v]
    lines.append("services: " + " ".join(svcs) + f"; claims: {' '.join(k[7:] for k in f if k.startswith('claims.')) or '-'}")
    ptz = [k[4:] for k, v in f.items() if k.startswith("ptz.") and v]
    if f.get("ptz"):
        lines.append("ptz: " + " ".join(ptz) + f"; profile {d.get('ptz_profile')}")
    img = [k for k, v in f.items() if k.startswith("imaging.") and v]
    if img:
        lines.append("imaging: " + " ".join(img))
    other = [k for k in ("audio", "backchannel", "snapshot", "events.pullpoint", "relays") if f.get(k)]
    lines.append("other: " + (" ".join(other) or "-"))
    for n in ctx.notes:
        lines.append("note: " + n)
    return "\n".join(lines)


def write(out: pathlib.Path, ctx, results, argv):
    out.mkdir(parents=True, exist_ok=True)
    meta = {
        "tool": "onvifcheck", "time": dt.datetime.now().isoformat(timespec="seconds"),
        "argv": argv, "target": ctx.name, "host": ctx.host, "port": ctx.port,
        "device": ctx.data.get("info", {}), "macs": ctx.data.get("macs", []), "mac_ok": ctx.mac_ok,
        "scopes": ctx.data.get("scopes", []), "features": ctx.features,
        "time_offset_s": ctx.data.get("time_offset"), "notes": ctx.notes,
        "summary": summary(results),
    }
    rows = [{
        "id": r.test.id, "official": r.test.official, "title": r.test.title, "service": r.test.service,
        "category": r.test.cat, "status": r.status, "duration_ms": round(r.duration * 1000),
        "calls": r.calls, "clients": ",".join(r.test.clients), "profiles": ",".join(r.test.profiles),
        "ref": r.test.ref, "messages": r.messages, "schema_errors": r.schema, "zeep_dropped": r.lost,
        "ops": r.ops,
    } for r in results]
    (out / "results.json").write_text(json.dumps({"meta": meta, "results": rows}, indent=1, default=str),
                                      encoding="utf-8")
    with open(out / "results.csv", "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(["id", "official", "title", "service", "category", "status", "clients", "profiles",
                    "duration_ms", "ops", "messages", "schema_errors", "zeep_dropped"])
        for x in rows:
            w.writerow([x["id"], x["official"], x["title"], x["service"], x["category"], x["status"],
                        x["clients"], x["profiles"], x["duration_ms"], " ".join(x["ops"]),
                        " | ".join(x["messages"]), " | ".join(x["schema_errors"]),
                        " | ".join(x["zeep_dropped"])])
    md = [f"# onvifcheck: {ctx.name}", "", f"{meta['time']}, `{' '.join(argv)}`", "",
          "```text", features_text(ctx), "```", "", f"**{meta['summary']}**", "",
          "| Status | Test | Title | Notes |", "|---|---|---|---|"]
    for r in results:
        note = "; ".join(m for m in r.messages if m.startswith(("FAIL", "WARN")))[:300]
        if r.schema:
            note += f" schema: {r.schema[0][:150]}"
        if r.lost:
            note += f" zeep drops: {'; '.join(r.lost[:3])}"
        if r.status in (NA, SKIP):
            note = "; ".join(r.messages)[:200]
        md.append(f"| {r.status} | {r.test.id} | {r.test.title} | {note.replace('|', '/')} |")
    (out / "summary.md").write_text("\n".join(md) + "\n", encoding="utf-8")
    tr = out / "trace"
    tr.mkdir(exist_ok=True)
    for i, rep in enumerate(ctx.client.log, 1):
        name = f"{i:04d}-{str(rep.service).rsplit('/', 1)[-1]}-{rep.op}.xml"
        (tr / name).write_text(
            f"<!-- POST {rep.url} -> HTTP {rep.status} {rep.elapsed * 1000:.0f} ms {rep.error} -->\n"
            f"<!-- request -->\n{_redact(rep.request)}\n<!-- response -->\n{rep.text}\n", encoding="utf-8")


def _redact(x: str) -> str:
    import re
    return re.sub(r"(<(?:\w+:)?Password[^>]*>)[^<]*(<)", r"\1***\2", x)
