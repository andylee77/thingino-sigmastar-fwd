# JL12D2 IR-cut mechanism

> **Verdict (live-tested 2026-10-27).** The JL12D2 has an **integrated IR-cut /
> AF / zoom head** on the D7 UART (`/dev/ttyS2`). The head moves the physical
> IR-cut filter, **commanded over that serial link**: the SoC streams it a
> 16-byte AF frame, one per sensor frame, whose **byte 11 is day (`00`) or night
> (`01`)**, and the head flips the filter (and refocuses for the IR shift). On
> the stock firmware the day/night command **fans out to two branches**, and
> the gpio one is a **dead end on this PTZ**:
>
> 1. **`media_server` branch:** `/dev/irled` (char major 93) pulses gpio 11/80,
>    plus the ISP colour/mono switch through **MI `0x1004`**. The **gpio pulse is
>    vestigial** (the D5 IR-cut header is unpopulated; gpio 80 is a SAR pad that
>    reaches nothing), and the ISP part only changes colour and mono in
>    software. This branch does **not** move the filter.
> 2. **`comm_server` branch:** **byte 11 over `ttyS2` to the head, which moves
>    the filter.** This is the real actuator.
>
> **Live proof:** writing `/dev/irled` from a shell (gpio only) changed nothing
> on the live image; the web `setIRCutManual_DayNight` SOAP call did, and byte 11
> flipped `00` to `01` with it.
>
> **Thingino:** raptor's day/night controller `ric` drives the same two gpios,
> which is why the port was pink in daylight until `lensd` set byte 11 itself.
> `lensd` now mirrors ric's day/night state into bytes 11 and 13 of every AF
> frame (§5). An earlier note that `printf > /dev/irled` flipped the filter was a
> misobservation and is disproven here.

## Why this exists

The question went round a circle: serial, then gpio, then serial. The first RE
pass assumed the stock firmware sent a **serial** IR-cut command to the
integrated head over D7, and that was right. A detour then chased a gpio theory
(a bistable H-bridge, pad drive strength, the pad mux, the driver's init), based
on an unverified note that `printf > /dev/irled` had flipped the filter. A live
gpio-only test disproved it. Tracing only `media_server` (§2) is what made that
pass conclude "no serial command, it's gpio". This document holds the evidence
so the question is not reopened: on the JL12D2 the gpio pins are a signal, and
the serial byte is the actuator.

## 1. Kernel `/dev/irled` driver (char major 93)

Tooling: **Ghidra 12.1 headless** (REA's Windows Ghidra rejects raw ARM; see the
Appendix). The raw kernel `Image` is mapped at base `0xC0008000`, with Thumb-2
forced across the whole image so cross-references resolve. Driver banner string:
`IRLED driver v2.1  20230517 for L12D`.

- **Registration:** `register_chrdev_region(MKDEV(93,0)=0x5d00000, 1, "IRLED")` +
  `cdev_init(cdev@0xC03ED398, fops@0xC03ED2F8)` + `cdev_add`.
- **fops @`0xC03ED2F8`:** `read = 0xC014A278`, `write = 0xC014A1E8` (owner/llseek/ioctl null).
- **init (`FUN@0xc0398840`):** `gpio_request(11,"IRCUT A")`, `(80,"IRCUT B")`,
  `(23,"IRDET")`; `gpio_direction_output(11,0)`, `(80,0)`; `gpio_direction_input(23)`;
  then **prime DAY, NIGHT, DAY**; a wifi-power gpio; register the cdev. No special
  pad, drive, power or clock configuration.
- **write(byte)** (`FUN_c014a1e8`): `get_user` 1 byte, then:
  - `0x01` = **DAY** (`FUN_c014a180`): `gpio_set(11,0); gpio_set(80,0); gpio_set(80,1)`,
    then arm a kernel timer (about +250 ms).
  - `0x00` = **NIGHT** (`FUN_c014a118`): the same on gpio 11.
  - `0x02` = reset.
  - The shared timer callback `FUN_c014a008` drops **both** pins low (ends the pulse).
  - The init-time busy-wait variants `FUN_c014a060`/`c014a0bc` do both low, 250 ms,
    active high, 250 ms, low.
- **read()** (`FUN_c014a278`): returns the status `0/1/2` ("irled_status").
- Every drive is `gpio_to_desc(n)` then `chip->set` (at `gpio_chip+0x2c`), that is
  plain `gpio_set_value`. **No UART, I²C, pad-drive register, regulator or clock
  anywhere in the driver.**
- gpio descriptor table @`0xC03ED1E0`: `[+4]=11` (`PAD_SPI0_DI`), `[+0x48]=80`
  (`PAD_SAR_GPIO1`), `[+0x8c]=23` (`PAD_PM_IRIN`).

## 2. Userspace `media_server` day/night path

`media_server` is an ARM ELF with no symbol table, but it is rich in log strings,
so Ghidra named the functions by cross-reference.

- `drv_ircut_set_day_mode` (`FUN_0003a488`): `write(irled_fd@struct+0x15dc, 0x01, 1)`.
- `drv_ircut_set_night_mode` (`FUN_0003a658`): `write(irled_fd, 0x00, 1)`.
- `drv_ircut_check_infrared_board_status` (`FUN_0003a3e4`): `read(irled_fd, &status, 4)`.
- `ircut_switch_daynight` (`FUN_0003a69c`): DAY calls `FUN_0003a308` then
  `set_day_mode`; NIGHT calls `FUN_0003a33e` then `set_night_mode`.
- `FUN_0003a308` / `FUN_0003a33e` call a common helper (`FUN@0x1f2cc0`) that builds an
  **MI command struct `{size=0x18, 0x04, cmd=0x1004, handle, payload}`** and
  dispatches it: the ISP **colour/night-mode** switch (payload `0` day, `1` night).
  A sibling helper uses MI cmd `0x1005`. This is a kernel **MI ioctl**, not a serial
  write.
- `g_ircutset_byafcmd` (`FUN_0003adf8`): **parses incoming AF frames** (head to host).
- `media_server` opens `ttyS2` (fd 21), but its day/night path writes **only**
  `/dev/irled` (gpio) and the **MI ISP ioctl**: no `ttyS2` write **from media_server**.

> **This section is only branch 1 of the fan-out** (see the Verdict). The
> day/night filter command is sent by a **different process, `comm_server`**, as
> byte 11 of the AF frame (§6). This `media_server` branch does the vestigial gpio
> pulse and the software ISP colour/mono switch (MI `0x1004`). The physical filter
> is **not** latched by gpio here.

## 3. Live confirmation (an OEM bench unit, on an OEM shell)

Kernel `5.10.61 #132`, hostname `IPCAM-XXXXXX-JL12D2_V100_AF` (the six MAC digits
blanked). Live `/proc/<pid>/fd`:

- `media_server` (pid 750): **fd 15 is `/dev/irled`, fd 21 is `/dev/ttyS2`**.
- `comm_server` (pid 775): **fd 6 is `/dev/ttyS2`** (the Pelco-D and lens channel).
- `/dev/ttyS2` is `ms_uart`, major `250,2`.

A ptrace write/read tracer (`ttysniff`, cross-compiled static ARM) was run on the
same OEM unit during real day/night flips. §6 has the result: it found the
day/night byte on `comm_server`'s `ttyS2` stream.

## 4. Hardware wiring (board inspection and the connector pinout)

- **D5 "IR-CUT" 2-pin gpio header: unpopulated** on the PTZ. So gpio 80 and 11
  reach **nothing**, and the kernel's gpio pulse is vestigial on this model.
- **D6 lighting header:** pins labelled CDSIN (CdS light-sensor input), PWM1 (IR)
  and PWM0 (warm/white). These are the header's labels; the Thingino board tree
  drives the IR bank from SoC PWM4 and the white bank from SoC PWM0.
- **D7 I/O and UART:** GND, TX and RX wired (SPKEN and red/blue not connected).
  **D7 is `ttyS2`, the one control link to the integrated IR-cut/AF/zoom head:**
  AF frames, Pelco-D pan, tilt and lens commands, **and the day/night byte**, all on
  one port at 57600 8N1. There is no baud switching: a sweep of the head at 9600,
  38400 and 115200 was silent ([JL12D2-PTZ-PROTOCOL.md](JL12D2-PTZ-PROTOCOL.md)).
- **D7 is not the boot console.** The console UART is `ttyS0` at 115200, on pads
  next to the SoC.

## 5. Thingino daytime pink — cause and fix

**Cause.** The physical filter moves only on **byte 11 of the serial AF frame to
the head**, not on gpio. Thingino's `ric` pulses gpio 80 (day) and gpio 11
(night), which reach nothing on this PTZ, and before the fix nothing sent byte 11.
The head never flipped the filter, so in daylight the filter stayed out, IR
reached the sensor and the picture was **pink**. The ISP colour switch Thingino
does is software only; without the physical filter it cannot remove the IR.

Live proof (stock firmware, watched on the live image): `printf '\000'` or
`'\001' > /dev/irled` (gpio only) gave **no day/night change**; the
`setIRCutManual_DayNight` SOAP call changed the image and flipped byte 11. So the
gpio is confirmed vestigial here.

**Fix, as built (`thingino-lensd`).** `lensd` already streams the AF frame to the
head. It sets **byte 11** (`00` day, `01` night) and **byte 13** (`00` day, `0x32`
night) in every frame and recomputes the byte-sum checksum (§6). It takes the mode
from ric's own pins, so ric and `raptor.conf` need no change:

- `S33lensd` starts lensd in its `af` mode (the JL12D2's head) with ric's two pins,
  read from `raptor.conf` `[ircut]`: `gpio_ircut` as `-d` (day) and `gpio_ircut2`
  as `-n` (night), 80 and 11 on the JL12D2. lensd has no pins compiled in.
- Before each frame lensd reads `/sys/class/gpio/gpio<n>/value`: day pin high
  means day, night pin high means night, both low (at rest) keeps the last mode.
  The gpio pulse stays, as the signal lensd reads.
- The pins pulse only on a change, so `S33lensd` asks ric for its current state
  (`raptorctl ric status`) and passes it as `-m day` or `-m night`. Without it, a
  lensd started after dark kept the filter in and the night picture went dark
  until the next change.
- The `day` and `night` commands on lensd's FIFO (`/run/lensd.cmd`) set the mode
  by hand.

A bench test of the Thingino image on 2026-11-06 passed with the IR-cut moving
through the head.

## 6. Live ttyS2 wire capture (2026-10-27)

Captured on the OEM firmware with `ttysniff` (ptrace) while forcing day to night
through the web `setIRCutManual_DayNight` SOAP endpoint.

- **`media_server` fd 21 (`/dev/ttyS2`): 0 reads, 0 writes** across two flips. It
  opens the port but does not use it.
- **`comm_server` fd 6 (`/dev/ttyS2` at 57600) is the live AF/lens channel:** a
  steady write stream of 16-byte frames, one per sensor frame:

  ```text
  byte   0  1  2  3  4  5  6     7     8     9     10 11  12 13  14 15
  value  51 01 04 78 01 0d FVa_H FVa_L FVb_H FVb_L 01 B11 03 B13 00 CK
  ```

  - `FVa` / `FVb` (bytes 6-9): the two AF focus values the SoC computes from AF
    windows 0 and 1 of the ISP statistics and sends to the head
    ([JL12D2-PTZ-PROTOCOL.md](JL12D2-PTZ-PROTOCOL.md) has the formula). They
    change every frame and **swung hard for about 1 s** at the day-to-night
    change: [I] the head refocusing for the IR shift, since they are image focus
    statistics and move when the focus moves.
  - Byte 10 was `01` throughout this capture; JL12D2-PTZ-PROTOCOL.md names it `L`.
  - **`B11` (byte 11) is the day/night flag: `00` day, `01` night.** It flipped
    `00` to `01` within about 124 ms of the NightMode command and held steady in
    each state. JL12D2-PTZ-PROTOCOL.md calls this byte `S1`.
  - **`B13` (byte 13)** went to `0x32` about 1 s into night (a night-mode
    parameter; `00` by day). JL12D2-PTZ-PROTOCOL.md calls it `S3`.
  - `CK` is the checksum.
- The day/night signal is **not** a separate command frame. It is the `B11`/`B13`
  fields **embedded in the running AF frames** (cmd `0x7801`; `"AF"` maps to `0x78`
  in `comm_server` `FUN_00018598`), which is why earlier passes missed it among
  the AF frames. The head reads byte 11 and drives the physical IR-cut filter.
- **Checksum = plain byte sum** of bytes 0-14 (verified: `Σ(51 01 04 78 01 0d d2 3c 52
  5a 01 00 03 00 00) mod 256 = 0x9a`, the captured last byte). Encoder:
  `comm_server` `FUN_0003e6b0` writes `Q(0x51) 01 04 cmdHi cmdLo len payload… sum`.
- **gpio-only cross-check:** writing `/dev/irled` from the shell changed neither the
  image nor byte 11; only the SOAP command did. The gpio is vestigial and byte 11
  is the actuator.
- Not to be confused with the N803: its head sends a stream with the same
  `51 01 04 78` header back to the SoC as status, and takes only Pelco-D
  commands (`N803-LENS-PROTOCOL.md`).

### Control chain (decompiled, `libtools.so` / `comm_server`)

Day/night (web `cgi_set_ircutmode` / `CMD_IRCUT_CONTROL`, state file
`/tmp/ircut_night_mode`) **fans out to two branches**:

1. `SetIRCUTControl` calls `fill_media_msgbuf(0x128)` and `MediaMsgSend` to
   **media_server**, which drives the `/dev/irled` gpio (vestigial) and the ISP
   `MI 0x1004` (colour/mono, software).
2. `MsgSetIRCUTControl` sends SysV `msgsnd` **cmd `0x416`** to **comm_server**, which
   sets the day/night state that becomes **byte 11** of the AF frame, and **the
   head moves the filter.** This is the real actuator.

Thingino's `lensd` takes the place of branch 2 (§5).

## Appendix — tooling notes

- **REA on Windows cannot decompile ARM.** Its Ghidra provider accepts only native
  PE and raw 6502 (`"Windows Ghidra P0 accepts native PE and explicitly selected raw
  6502 targets only"`); Hopper is macOS-only; IDA and Kuna are not configured. Drive
  **Ghidra 12.1 headless** directly instead.
- **Headless recipe (raw kernel):**
  `analyzeHeadless <proj> <name> -import Image -processor ARM:LE:32:v7 -loader
  BinaryLoader -loader-baseAddr 0xC0008000 -preScript SetThumbMode.java -postScript
  Dump*.java`. `SetThumbMode` sets `TMode=1` over the whole block, which gives
  Thumb-2 decoding and movw/movt cross-reference resolution (what an earlier ad-hoc
  Ghidra run missed). ELF userspace binaries import plainly (no base or Thumb
  forcing).
- The OEM kernel is an **XZ** uImage (not plain lzma). Header load address
  is `0x20008000`; the kernel's runtime virtual base is `0xC0008000`.
- **OEM debug shell:** the live work of §3 and §6 ran on a root shell opened on
  the stock OEM firmware. How it is opened is kept in the private security
  notes, not here.
- The raw register and serial dumps, the Ghidra scripts and the `ttysniff` tracer
  source are not published.

## Unverified

No open fact has its home in this document, and as an exported document it
states none. One related point is worded neutrally here: the AF-frame rate of the
stock firmware. Records disagree on it, and its home is
[JL12D2-PTZ-PROTOCOL.md](JL12D2-PTZ-PROTOCOL.md) (U-29), so this document says
only "one per sensor frame".
