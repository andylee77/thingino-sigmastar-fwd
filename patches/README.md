# Patch export

The two patch series that the public repo
[andylee77/thingino-sigmastar-fwd](https://github.com/andylee77/thingino-sigmastar-fwd)
carries in `patches/`: the SigmaStar Infinity6C port of
[Thingino](https://github.com/themactep/thingino-firmware) and its
[raptor-hal](https://github.com/gtxaspec/raptor-hal) backend. They are a
derived export: code is written on the development branch `sigmastar-fwd` and
the raptor-hal fork's `sigmastar` branch, never in a patch file, and a fix goes
into its source before the series is regenerated. This file is published with
the series unchanged, so it names no private path or document; the script
paths below are the development repo's, which is not published.

## The two series

| Directory | Patches | Applies onto | Made from |
|---|---|---|---|
| [`thingino-sigmastar/`](thingino-sigmastar/) | 22 | `themactep/thingino-firmware` at `b9b040f33` | branch `sigmastar-clean2`: the tree of the publish branch `sigmastar-publish`, cut by path into one commit per group |
| [`raptor-hal/`](raptor-hal/) | 13 | bare `gtxaspec/raptor-hal` at `9f09664` | the fork's branch `sigmastar-publish`: the tree of its `sigmastar` tip, with the commits that touch only `FORK.md` folded into one |

- `sigmastar-publish` is its own merge of the upstream base plus the SigmaStar
  commits of `sigmastar-fwd`, cherry-picked in order. Generic fixes stay out of
  the bundle, kept for upstream pull requests of their own.
- The groups run from the platform (vendor packages, board and kernel, config,
  toolchain, utilities, the raptor-hal build) through the changes to shared
  Thingino packages to one patch per camera profile.
- The raptor-hal series carries the two commits that vendor John Chia's MI
  headers and Infinity6C backend, so it applies to the bare upstream and gives
  the fork tree the firmware series pins (`6f00723`, read 2026-11-11).

## Base and drift

`git format-patch` writes no base line, so the bases are named here.
`bundle-regen.sh` leaves this file as it is: whoever regenerates the series
rewrites this section by hand (the bases and the dated drift note) before the
series is published, in the refresh step of "Regenerate the export" in the
development repo's publishing guide.

- **Bases of this export** (cut 2026-11-11, last after that day's landing of
  ipud's outputs and lensd's absolute zoom): `thingino-sigmastar/` on upstream
  master `b9b040f33` (2026-11-11; `sigmastar-clean2~22`), `raptor-hal/` on
  gtxaspec `main` `9f09664` (2026-10-31). The HAL series is 13 patches. The
  export before it was cut on 2026-11-06, on `13ad43c31`, with 21 patches; the
  22nd is new, `thingino-ipud`.
- **Drift.** The development branch keeps moving; the export moves only when
  it is regenerated, and the automatic upstream sync does not advance the
  publish branch. `thingino/scripts/check-bundle-drift.sh` (WSL; its header
  gives the four tests) says whether the export still matches its sources:
  the Thingino series applies cleanly to its base and gives the tree of the
  publish branch (and of `sigmastar-clean2`); the HAL series applies cleanly
  to its base and gives the tree of the fork commit the publish branch pins
  in `thingino-raptor-hal.mk` (and of the fork's `sigmastar` tip); every
  development commit is on the publish branch and listed `include` in
  `commits.txt`, or listed `exclude`, and every publish-only commit is listed
  `publish`; every fork commit is a patch of the HAL series or touches only
  `FORK.md`. It commits, moves and pushes nothing.
- **On 2026-11-11** the drift check passes every test: both series apply
  cleanly to their bases and give the trees named above, and every
  development commit is classified. `2b353000b`, four schema-order fixes to
  thingino-onvif's answers, is in neither series: it goes to thingino-onvif
  upstream on its own.
- **The current bases** are on the development repo's generated state page,
  in its Publishing section, read from the `BASE` and `HAL_BASE` defaults of
  `bundle-regen.sh`. The drift result is not there: only a run of the drift
  check gives it.

## Regenerating

`thingino/scripts/bundle-regen.sh` (WSL; its header gives the steps and
defaults) rebuilds `sigmastar-clean2` from `sigmastar-publish` with the groups
of `thingino/scripts/bundle/groups.txt`, and the fork's `sigmastar-publish` on
`HAL_BASE`, with fixed identity and dates, so the same inputs give the same
SHAs. It replaces every `*.patch` here (this file stays), runs
`check-bundle-scrub.sh` and the drift check, and pushes nothing.

Every new development commit is classified first in
`thingino/scripts/bundle/commits.txt`: SigmaStar work is cherry-picked onto
`sigmastar-publish` and listed `include`, generic work `exclude`, and a commit
made on the publish branch first `publish` until it lands on the development
branch. The drift check fails until each one is classified.

The full procedure (tagging the replaced refs `bundle/pre-*`, merging a new
base, fixing a scrub hit at its source, assembling and checking the public
tree, the approval before any push) is "Regenerate the export" in the
development repo's publishing guide.

## Known limits

- **Not buildable as is.** The build fetches the vendor packages, kernel,
  toolchain and sensor headers from `file://$(HOME)/src/mirrors/...` (mirrors
  of John Chia's kernel, SDK, library and toolchain release, and of
  `openipc/sensors`) and raptor-hal from `file://$(HOME)/src/forks/raptor-hal`
  (read from the patches, 2026-11-09). An outside reader cannot fetch them.
- **In no patch:** the OEM sensor tunings (`gc8613.bin`, `gc4653.bin`, the
  N803's IMX415 tuning), which are vendor files; SigmaStar's sensor-framework
  headers, which the `sigmastar-sensor-headers` package fetches at build time;
  firmware images, of which none are published (source and build instructions
  only).
- **Licensing** was decided on 2026-11-06: each contribution takes the license
  of the project it modifies and, where files differ, of the file it modifies
  or lands in. The license therefore follows the path a hunk touches, not the
  series or the patch, and one patch can carry more than one. The per-path
  map is in the license files that join the series when it is published: a
  `LICENSE.md` in each series directory and the repo's `NOTICE.md`; a file's
  own license statement wins over both.
