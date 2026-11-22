# Reaching the cameras

How the work behind this port reaches its cameras: a bench of test units and
a set of deployed ones, across two SoC families (SigmaStar Infinity6C and
Ingenic T31/T41), all running Thingino. Every shell command, file copy, build
check and RAM-only test goes through one small command-line tool, `cam`, on a
Windows workstation that builds in WSL and keeps the Git Bash and WSL traps
out of the way with a few wrappers and hooks. None of these tools are in this
repository yet; this page describes what they do and why, so the approach can
be copied or the tools asked for.

## Why one tool

Plain `ssh` and `scp` against a growing set of cameras failed in the same few
ways again and again:

- **Addresses drift.** Cameras take DHCP leases, so an IP written in a note or
  a script points at a different unit a week later. A command meant for a test
  unit can land on a deployed one.
- **Copies were not checked.** A truncated library or daemon staged on a unit
  looks like a code bug.
- **Quoting.** A multi-line script passed through a Windows shell, then SSH,
  then BusyBox `sh` loses its quotes or gains carriage returns.
- **No overview.** Which unit runs which build had to be found by hand.

`cam` fixes each one in a single place: units are named and found by MAC,
every transfer is checksummed, scripts go over stdin, and one command reads
the build of every unit at once.

## Naming a unit

Every camera has one name: `MODEL-XXXX`, the model plus the last four hex
digits of its identity MAC, upper case. The identity MAC is `eth0`'s, or
`wlan0`'s on a Wi-Fi-only camera. The name survives a reflash, a new IP and a
new hostname. Hostnames (the OEM's or Thingino's), profile names and IPs are
aliases at most, never the name.

Examples below use `MODEL-1A2B` and `<camera-ip>`.

## The fleet file

`cam` reads one JSON file, `cam-fleet.json`, kept beside the tool (or named by
`$CAM_FLEET`). It is the roster:

```json
{
  "subnets": ["<bench-subnet>/24", "<production-subnet>/24"],
  "defaults": { "user": "root", "passwords": ["<kept out of every repo>"] },
  "units": {
    "MODEL-1A2B": {
      "mac": "AA:BB:CC:DD:EE:FF",
      "model": "...", "vendor": "...", "soc": "...",
      "role": "what the unit is for",
      "status": "bench | deployed | shelved | retired",
      "segment": "bench | production",
      "layout": "flash layout note",
      "last_ip": "...", "last_seen": "...",
      "last_build": "...", "last_image": "..."
    }
  }
}
```

- People edit the names, MACs, roles and status by hand. `cam` writes only its
  cache fields (`last_ip`, `last_seen`, `last_build`, `last_image`), through a
  temporary file and a rename, so two runs at once cannot tear it.
- A unit that is not in the file is not reachable by name. A bare IP is refused
  unless `--raw-ip` is given, so a mistyped address cannot quietly reach the
  wrong camera.
- Credentials live only in this file on the workstation. They never go on a
  command line, in a note or in a repository.

## How a unit is found

`cam MODEL-1A2B ...` (or just `cam 1a2b ...`, or the MAC) does this:

1. Connect to the cached `last_ip` over SSH.
2. Read every interface's MAC from `/sys/class/net/*/address` and check that
   the fleet file's MAC is among them. A match means the right camera: run
   the command. (Reading only `eth0` failed on a Wi-Fi-only board whose
   unused `eth0` carries a bootloader placeholder address.)
3. On a mismatch or no answer, rediscover:
   - probe port 22 on every host of the listed subnets in parallel and keep
     the SSH banners;
   - on subnets the workstation shares a link with, the ARP table maps MAC to
     IP directly;
   - on routed subnets, where ARP does not help, log in only to hosts whose
     banner says `dropbear` (Thingino's SSH server) and read their MAC. Other
     SSH hosts are listed and never logged in to.
4. Record the new IP and carry on. `cam find` runs the sweep for the whole
   fleet and names any dropbear host that is not in the fleet file. Beside
   the sweep it browses Thingino's mDNS service, `_thingino._tcp`, on the
   subnets the workstation shares a link with, so an unknown Thingino
   camera is listed with its product and build. mDNS does not cross a
   router, and the sweep is about as fast, so it only labels; it finds
   nothing the sweep would not.

## Commands

| Command | What it does |
|---|---|
| `cam list` | The roster: name, model, MAC, last IP, last seen. |
| `cam find [NAME...]` | Rediscover IPs by MAC and update the cache. |
| `cam NAME 'cmd'` | Run one command in the unit's shell, stream its output, exit with its status. |
| `cam sh NAME [ARGS...] <<'EOF'` | Run a script fed on stdin: no size limit, no nested quoting; carriage returns are stripped. |
| `cam push NAME LOCAL REMOTE [MODE]` | Upload a file, MD5-checked on both ends. |
| `cam pull NAME REMOTE LOCAL` | Download a file, MD5-checked. |
| `cam info NAME` | MAC, hostname, uptime, build, `/proc/mtd` and the flash layout note. |
| `cam builds [NAME...]` | Read-only: every unit's `BUILD_ID` and `IMAGE_ID`, probed in parallel. |
| `cam upgrade NAME IMAGE [--rootfs]` | Push an image, run the unit's own `sysupgrade`, wait for it to answer and print the new `BUILD_ID`. |
| `cam web NAME [--revoke]` | Create a web UI session in the unit's RAM session store for browser-based testing, without typing a password. |

Options go before the verb: `-t SECS` (command timeout, default 120),
`--user`, `--no-verify` (skip the MAC check), `--raw-ip`. The exit status is
the remote command's; 255 means no connection and 124 a timeout, so `cam`
works in scripts like `ssh` does.

### File transfer without scp

`cam push` and `cam pull` do not rely on `scp` or an SFTP subsystem. They
stream the file over a plain SSH exec channel (`cat > file && md5sum file`)
and compare the remote MD5 with the local one; a mismatch is an error, never
a warning. The same path works on every Thingino build regardless of what
the SSH server offers.

### Scripts

A heredoc goes to the unit as is:

```sh
cam sh MODEL-1A2B <<'EOF'
logread | tail -n 50
grep -E '^(BUILD_ID|IMAGE_ID)=' /etc/os-release
df -h /tmp
EOF
```

## What each unit runs

Each image of this port stamps `BUILD_ID` in `/etc/os-release` with the
branch and commit it was built from, and `-dirty` when the tree had
uncommitted changes (patch `[0017]`), for example
`sigmastar-fwd+87ed9ba, <date>`. `cam builds` reads it from every unit in a
few seconds; units marked shelved or retired are skipped unless named.

A small drift script then compares each build with the development branch
and reports, per unit:

- **lacks N of ours**: commits of this port's branch the build does not have,
  split into generic and SoC-specific by the files they touch. An Ingenic
  unit is judged on the generic ones only;
- **+N own**: commits in the build that are not on the branch (a
  feature-branch build);
- **master -N**: upstream Thingino commits the build does not have.

Both run at the start of every working session, so the picture of the fleet
is never older than the session.

## Testing without a reflash

Most changes are tried in RAM first, with nothing written to flash:

1. Build only the package (a library or a daemon), not an image.
2. `cam push` it to `/tmp` on a bench unit.
3. Restart the streamer against it: `LD_LIBRARY_PATH=/tmp/...` for a
   library, a bind mount over the installed binary for a daemon, `insmod`
   for a kernel module.
4. Collect `dmesg` and `logread` with `cam sh`.

A reboot clears all of it. Deployed units are restored and checked after each
test; bench units may keep a staged file until the work lands.

## Guard rails

- **`cam` only.** A shell hook on the workstation refuses raw `ssh` and `scp`
  to any fleet camera and says which `cam` command to use instead.
- **Flashing is deliberate.** `cam upgrade` uses the unit's own `sysupgrade`,
  is run only by hand and per unit, and checks that `BUILD_ID` changed. On the
  SigmaStar units the OEM bootloader partition is never written. Flashing
  procedures are not part of this repository.
- **The roster changes by hand.** New units, names, roles and credentials are
  edited by a person; the tool keeps only its cache.
- **Bench and production are separate segments.** Test units sit on a bench
  network; deployed units feed a video recorder, so any test on one says what
  it does to the live view and puts it back afterwards.

## The workstation: Git Bash and WSL

The work runs on a Windows workstation. Shell work, `cam` and the session
scripts run in Git Bash; the Thingino trees, Buildroot and every build live in
WSL (Ubuntu), on the Linux file system. Crossing between the two had its own
set of recurring failures, and each one is now fixed once, in a small wrapper
on the `PATH` or in a hook, rather than remembered in a note.

### The traps

- **MSYS path conversion.** Git Bash rewrites any argument that starts with
  `/` into a Windows path before it reaches a Windows program, so a WSL path
  such as `/opt/x` or a camera path such as `/tmp/x` arrives as
  `C:/Program Files/Git/...`.
- **`wsl.exe` re-parses its arguments.** Without `--exec`, `wsl.exe` joins
  argv into one string and hands it to the Linux login shell, so
  `wsl bash -lc '... $X ...'` has `$X` expanded too early and its quotes
  stripped.
- **Environment does not cross** without `WSLENV` bookkeeping.
- **CRLF.** A script written on the Windows side with CRLF line endings fails
  in bash or BusyBox `sh` with errors that do not mention line endings.
- **Lost exec bits.** Writing a file through the WSL network share from
  Windows drops its executable bit, so an init script or a CGI edited that
  way stops running.

### The wrappers

All three are short bash scripts in a directory that comes first on the Git
Bash `PATH`. They have no file extension, so Windows itself never picks them
up; only Git Bash does.

| Wrapper | What it does |
|---|---|
| `wsl` | A shim in front of `wsl.exe`: turns MSYS path conversion off, runs bare commands with `--exec` so what Git Bash passes is what Linux gets, and rewrites a whole argument that is a Windows path (`C:/x`, `C:\x`, `/c/x`) into its `/mnt/<drive>/` form. Management options (`-l`, `--shutdown`, ...) pass through untouched. Typing `wsl.exe` bypasses it, which is why a hook refuses that. |
| `wslrun [-C DIR] [NAME=VALUE ...] SCRIPT [ARGS]` | Runs a script in WSL under a login `bash -l`. The script can be a Windows path or a WSL path, or come on stdin as a heredoc; `NAME=VALUE` pairs are set in the WSL environment without `WSLENV`; the exit status is the script's; CRLF endings are warned about. The usual way to run anything multi-line in WSL. |
| `wslcp pull`, `push`, `diff` | Copies one file between Windows and WSL, MD5-checked. `push` keeps the destination's mode (a new file gets 0755 when git's index records it as executable), refuses a CRLF file unless told otherwise, and creates directories only with `--mkdir`. For editors and tools that will not write into the WSL share directly: pull a copy, edit it, push it back. |

`cam` uses the same idea: its wrapper turns path conversion off so remote
paths reach the camera intact, and converts only its own path to the Python
file by hand.

### The hooks

The coding agent that does much of this work runs every shell command through
two hooks. Both are small Python scripts, tested, and fail open (an error in a
hook never blocks work).

- **Before a shell command** (`bash_guard`): refuses, with the exact command
  to use instead,
  - `wsl.exe ...`, which bypasses the shim;
  - raw `ssh`, `scp`, `sftp`, `plink` or `sshpass` whose destination is a
    fleet camera, by fleet name, its last four hex digits, or any IP the
    fleet file has recorded for it. Only the destination counts (including
    jump hosts, `-o HostName`, and `ssh` inside a `wslrun` heredoc or a
    `bash -lc` string), so a camera name in a grep pattern or a URL is fine;
  - a command sent through the web UI's command endpoint that is over about
    1.8 KB, which the web server drops silently.
- **After a file edit** (`wsl_exec_bit`): when a file was written through the
  WSL share and git's index records it as executable, puts the exec bit back.

Every session also sets `PYTHONUTF8=1`, so Python tools print camera output
and non-ASCII text without encoding errors, and files meant for Linux or a
camera are written with LF endings.

### The session-start check

Each working session starts with one Git Bash script, run by a session-start
hook with a time cap. It ties the pieces above together:

1. `cam builds` reads every unit's `BUILD_ID` (read-only).
2. Through `wslrun`, a WSL script fetches upstream Thingino and the
   raptor-hal fork's upstream, runs the drift report against the
   development branch, and reports what moved. It never merges, rebases or
   moves a branch.
3. When upstream has moved past the last sync point, a separate sync script
   starts in WSL as its own hidden Windows process, so it outlives the hook:
   it merges upstream on a new branch and runs the host checks, and moves
   the development branch only when every check passes.
4. Generated status pages (the roster, branch heads, the fleet against the
   development branch) are rebuilt.

The report arrives as the first thing the session reads.

## Requirements

`cam` is a single Python 3 file with one dependency,
[paramiko](https://www.paramiko.org/), run on a Windows workstation through a
small Git Bash wrapper that keeps remote paths such as `/tmp/x` from being
rewritten into Windows paths. Nothing in the approach is Windows-specific:
the ideas (name by MAC, verify the MAC on every connect, checksum every copy,
read the build stamp fleet-wide) carry over to any SSH client. The WSL
wrappers matter only on a Windows host that builds in WSL.
