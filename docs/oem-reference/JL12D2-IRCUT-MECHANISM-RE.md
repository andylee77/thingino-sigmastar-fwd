# JL12D2 IR-cut mechanism — definitive RE (kernel + userspace)

> **Verdict (2026-10-27, live-tested — final, correct conclusion).** The JL12D2 is
> an **integrated IR-cut / AF / zoom HEAD** on the D7 UART. The physical IR-cut
> filter is moved by that head, **commanded over the serial link**: `comm_server`
> sends the head a 25 Hz AF frame whose **byte 11 = day(`00`) / night(`01`)**, and
> the head flips the filter (and refocuses for the IR shift). The OEM day/night
> command **fans out to two branches**, and the gpio one is a **dead end on this PTZ**:
>
> 1. **`media_server` branch** — `/dev/irled` (major 93) pulses gpio 11/80, plus ISP
>    colour/mono via **MI `0x1004`**. The **gpio pulse is VESTIGIAL** (D5 IR-cut
>    header UNPOPULATED; gpio-80 = SAR pad reaches nothing); the ISP part only
>    changes colour↔mono in software. This branch does **not** move the filter.
> 2. **`comm_server` branch** — **byte 11 over ttyS2 → the head → the physical
>    filter.** This is the real actuator.
>
> **Live proof:** writing `/dev/irled` from the shell (gpio only) caused **no**
> day/night change (user watching); the web `setIRCutManual_DayNight` SOAP did, and
> byte 11 flipped `00`→`01` with it. **This is why Thingino is daytime-pink:** `ric`
> pulses the dead gpio and never sends byte 11. **Fix: `lensd` must set byte 11
> (day/night) in its AF frames.** (A prior "it's gpio / printf flipped the filter"
> note was unverified and is disproven here.)

## Why this exists

The task that opened this session assumed the OEM sent a **serial** IR-cut command
to the integrated head over D7 — and that turned out to be **right**. A mid-session
"it's gpio" detour (based on an unverified prior note that `printf > /dev/irled`
flipped the filter) was wrong and was disproven by a live gpio-only test. This
document is the single source of truth so the circle (serial → gpio → serial)
doesn't repeat.

## 1. Kernel `/dev/irled` driver (char major 93)

Tooling: **Ghidra 12.1 headless** (REA's Windows Ghidra rejects raw ARM — see
Appendix). Raw kernel `Image` mapped at base `0xC0008000`, Thumb-2 forced across the
whole image so cross-references resolve. Driver banner string:
`IRLED driver v2.1  20230517 for L12D`.

- **Registration:** `register_chrdev_region(MKDEV(93,0)=0x5d00000, 1, "IRLED")` +
  `cdev_init(cdev@0xC03ED398, fops@0xC03ED2F8)` + `cdev_add`.
- **fops @`0xC03ED2F8`:** `read = 0xC014A278`, `write = 0xC014A1E8` (owner/llseek/ioctl null).
- **init (`FUN@0xc0398840`):** `gpio_request(11,"IRCUT A")`, `(80,"IRCUT B")`,
  `(23,"IRDET")`; `gpio_direction_output(11,0)`, `(80,0)`; `gpio_direction_input(23)`;
  then **prime DAY → NIGHT → DAY**; a wifi-power gpio; register the cdev. No special
  pad/drive/power/clock config.
- **write(byte)** (`FUN_c014a1e8`): `get_user` 1 byte →
  - `0x01` = **DAY** (`FUN_c014a180`): `gpio_set(11,0); gpio_set(80,0); gpio_set(80,1)`
    then arm a kernel timer (+~250 ms).
  - `0x00` = **NIGHT** (`FUN_c014a118`): symmetric on gpio 11.
  - `0x02` = reset.
  - Shared timer callback `FUN_c014a008` drops **both** pins low (completes the pulse).
  - The init-time busy-wait variants `FUN_c014a060`/`c014a0bc` do both-low → 250 ms →
    active-high → 250 ms → low.
- **read()** (`FUN_c014a278`): returns status `0/1/2` ("irled_status").
- Every drive is `gpio_to_desc(n)` → `chip->set` (at `gpio_chip+0x2c`), i.e. plain
  `gpio_set_value`. **Zero uart / i²c / pad-drive register / regulator / clock
  anywhere in the driver.**
- gpio descriptor table @`0xC03ED1E0`: `[+4]=11` (`PAD_SPI0_DI`), `[+0x48]=80`
  (`PAD_SAR_GPIO1`), `[+0x8c]=23` (`PAD_PM_IRIN`).

Raw evidence: [`irled_dump.txt`](irled_dump.txt) (Ghidra decompile).

## 2. Userspace `media_server` day/night path

`media_server` is ARM ELF, no symtab, but name-rich via log strings (so Ghidra
named the functions by xref). Decompile evidence: [`media_ircut_dump.txt`](media_ircut_dump.txt).

- `drv_ircut_set_day_mode` (`FUN_0003a488`): `write(irled_fd@struct+0x15dc, 0x01, 1)`.
- `drv_ircut_set_night_mode` (`FUN_0003a658`): `write(irled_fd, 0x00, 1)`.
- `drv_ircut_check_infrared_board_status` (`FUN_0003a3e4`): `read(irled_fd, &status, 4)`.
- `ircut_switch_daynight` (`FUN_0003a69c`): DAY → `FUN_0003a308` then `set_day_mode`;
  NIGHT → `FUN_0003a33e` then `set_night_mode`.
- `FUN_0003a308` / `FUN_0003a33e` call a common helper (`FUN@0x1f2cc0`) that builds a
  **MI command struct `{size=0x18, 0x04, cmd=0x1004, handle, payload}`** and dispatches
  it — the ISP **colour/night-mode** switch (payload `0`=day, `1`=night). A sibling
  helper uses MI cmd `0x1005`. This is a kernel **MI ioctl**, not a serial write.
- `g_ircutset_byafcmd` (`FUN_0003adf8`): **parses incoming AF frames** (head → host).
- `media_server` opens `ttyS2` (fd21) but its day/night path writes **only**
  `/dev/irled` (gpio) + the **MI ISP ioctl** — no ttyS write **from media_server**.

> **This section is only branch 1 of the fan-out** (see the Verdict). The day/night
> filter command is sent by a **different process, `comm_server`** (byte 11 of the AF
> frame — §6); this `media_server` branch does the vestigial gpio pulse + the software
> ISP colour/mono (MI 0x1004). Tracing only `media_server` is what made an earlier pass
> wrongly conclude "no serial command / it's gpio." The physical filter is **not**
> latched by gpio here.

## 3. Live confirmation (on the OEM firmware)

Kernel `5.10.61 #132`, `IPCAM-XXXXXX-JL12D2_V100_AF`. Live `/proc/<pid>/fd`:

- `media_server` (pid 750): **fd15 → `/dev/irled`, fd21 → `/dev/ttyS2`**.
- `comm_server` (pid 775): **fd6 → `/dev/ttyS2`** (Pelco/lens channel).
- `/dev/ttyS2` = `ms_uart` major `250,2`.

A ptrace write/read tracer (`ttysniff`, cross-compiled static ARM) **was run** on
a Thingino unit during real day/night flips — see §6 for the result (it found the day/night
byte on comm_server's ttyS2 stream).

## 4. Hardware wiring (from the user's board + the connector pinout)

- **D5 "IR-CUT" 2-pin gpio header: UNPOPULATED** on the PTZ. So gpio 80/11 reach
  **nothing** — the kernel's gpio pulse is vestigial on this unit.
- **D6 lighting:** CDSIN (CdS light sensor in), PWM1 = IR, PWM0 = warm/white.
- **D7 I/O + UART:** GND + TX + RX wired (SPKEN / red-blue NC). **ttyS2 on D7 is the
  one control link to the integrated IR-cut/AF/zoom head** — AF, PTZ/lens, **and the
  day/night (IR-cut) byte**, time-multiplexed with baud switching (9600/57600/115200).

## 5. Thingino daytime pink — cause and fix

**Cause (settled):** the physical filter is actuated by **byte 11 of the serial AF
frame to the head**, not by gpio. Thingino's `ric` pulses the vestigial gpio 80/11
and **never sends byte 11**, so the head never flips the filter → in daylight the
filter stays out → IR contamination → **pink**. (The ISP colour switch Thingino does
is only software; without the physical filter it can't remove the IR.)

Live proof (user watching): `printf '\000'/'\001' > /dev/irled` (gpio only) →
**no day/night change**; `setIRCutManual_DayNight` SOAP → image changes and byte 11
flips. So gpio is confirmed vestigial here.

**Fix (Thingino `lensd`):** `lensd` already builds/sends the AF frames to the head —
make it set **byte 11 = `00` (day) / `01` (night)** (and byte 13 = `0x32` in night)
per the current day/night mode, with the trailing byte-sum checksum (§6). Drive byte
11 from `ric`'s mode (or `/tmp/ircut_night_mode`). Then retire the gpio toggle on this
profile (it does nothing). Verify on the bench, then on the deployed PTZ unit.

## 6. Live ttyS2 wire capture (2026-10-27)

Captured with `ttysniff` (ptrace) while forcing day→night via the web
`setIRCutManual_DayNight` SOAP endpoint on the OEM firmware.

- **`media_server` fd21 (`/dev/ttyS2`): 0 reads, 0 writes** across two flips — it
  opens the port but does not use it (confirms the old "fd21 = nothing" note).
- **`comm_server` fd6 (`/dev/ttyS2` @ 57600): the live AF/lens channel** — a steady
  **25 Hz** write stream, every frame 16 bytes:

  ```text
  51 01 04 78 01 0d  Fh Fl  Vh Vl  01  B11  03  B13  00  CK
  └──── header ────┘ └focus┘ └val─┘     day/night    night-param  cksum
  ```

  - `Fh Fl` / `Vh Vl` = live **AF focus / contrast telemetry** (fluctuate every
    frame; **sweep hard** for ~1 s at the day→night transition = the lens
    **refocusing** for the IR shift).
  - **`B11` (byte 11) = day/night flag: `00`=day, `01`=night.** Flipped `00→01`
    within ~124 ms of the NightMode command; constant across each steady state.
  - **`B13` (byte 13)** → `0x32` ~1 s into night (a night-mode parameter; `00` in day).
  - `CK` = checksum over the payload.
- The day/night signal is **not** a separate command frame — it is the `B11`/`B13`
  fields **embedded in the ongoing 25 Hz AF frames** (cmd `0x7801`; `"AF"`→`0x78` per
  `comm_server` `FUN_00018598`). That is exactly why earlier passes "missed it among
  the AF frames." The head reads byte 11 and drives the physical IR-cut filter (and
  refocuses — the `Fh/Fl/Vh/Vl` sweep at the transition).
- **Checksum = plain byte-sum** of the frame (verified: `Σ(51 01 04 78 01 0d d2 3c 52
  5a 01 00 03 00 00) mod 256 = 0x9a` = the captured last byte). Encoder:
  `comm_server` `FUN_0003e6b0` → `Q(0x51) 01 04 cmdHi cmdLo len payload… sum`.
- **gpio-only cross-check:** writing `/dev/irled` from the shell changed neither the
  image nor byte 11 (user watched); only the SOAP command did. → gpio vestigial, byte
  11 is the actuator.

### Control chain (decompiled, `libtools.so` / `comm_server`)

Day/night (web `cgi_set_ircutmode` / `CMD_IRCUT_CONTROL`, state file
`/tmp/ircut_night_mode`) **fans out to two branches**:

1. `SetIRCUTControl` → `fill_media_msgbuf(0x128)` + `MediaMsgSend` → **media_server** →
   `/dev/irled` gpio (vestigial) + ISP `MI 0x1004` (colour/mono, software).
2. `MsgSetIRCUTControl` → `msgsnd` SysV **cmd `0x416`** → **comm_server** → sets the
   day/night state that becomes **byte 11** of the 25 Hz AF frame → **the head moves
   the filter.** ← the real actuator.

**Implication for Thingino `lensd`:** see §5 — set byte 11 (and byte 13 in night) in
the AF frames; that is what flips the physical filter and fixes daytime pink.

## Appendix — tooling notes

- **REA on Windows cannot decompile ARM.** Its Ghidra provider accepts only native PE
  and raw-6502 (`"Windows Ghidra P0 accepts native PE and explicitly selected raw 6502
  targets only"`); Hopper is macOS-only; IDA/Kuna unconfigured. Drive **Ghidra 12.1
  headless** directly instead.
- **Headless recipe (raw kernel):**
  `analyzeHeadless <proj> <name> -import Image -processor ARM:LE:32:v7 -loader
  BinaryLoader -loader-baseAddr 0xC0008000 -preScript SetThumbMode.java -postScript
  Dump*.java`. `SetThumbMode` sets `TMode=1` over the whole block → Thumb-2 decode +
  movw/movt xref resolution (the thing the earlier ad-hoc Ghidra run missed). ELF
  userspace binaries import plainly (no base/Thumb forcing).
- `build/live_flash/kernel.bin` = **XZ** uImage (not plain lzma). Header load address
  is `0x20008000`; the kernel's runtime virtual base is `0xC0008000`.
- **OEM root shell** (needed for the live `/proc` and `ttysniff` captures above) was
  obtained out of band on the OEM firmware; the mechanism is tracked privately and is
  not reproduced here.
- Raw register and serial dumps, the Ghidra scripts, and the `ttysniff` tracer source
  are kept with the project and can be shared on request.
