# N803-HS5X — pad, GPIO & connector map

Authoritative hardware map for the **Anpviz / UVision N803** 5X-zoom PTZ dome
(module `N803`, product `Anpviz PTZIP…-5X-A 8MP`, firmware platform `N803-HS5X`).
Built for the Thingino port (`n803_ssc378qe_imx415`).

**SoC** SigmaStar **SSC378QE** (Infinity6C / i6c, DTB model `INFINITY6C SSC027D-S01A`,
U-Boot board tag `KL_LX510`). **Sensor** Sony **IMX415** (1/2.8" 8 MP, 4-lane MIPI,
MCLK 37.125 MHz). **DDR** 256 MB. **Flash** 16 MB SPI NOR.

Provenance tags per row:

- **DS** — vendor datasheet (uvision-tech / Remoteyes N803 module page + connector table).
- **KO** — OEM `/mnt/mtd/nsd/program/ko.sh`, **378 / else branch** (the active path on this
  board: `/sys/devices/soc0/machine` $2 = `SSC027D-S01A` ≠ `SSC027A-S01A`). GPIO numbers are
  SigmaStar MDRV numbering.
- **DT** — decompiled OEM device tree (harvested from the unit's flash).
- **PH** — physical board inspection (bench photos 2026-10-28/29).
- **CFG** — OEM `/customer/config/setting/*.conf`.

> ⚠ GPIO numbers are from the OEM firmware and are to be **confirmed with a live toggle**
> on the bench before they are trusted in the DTS. On the sibling MC-A85 (same SSC378/i6c)
> the OEM gpio 80/81 IR-cut numbers mapped 1:1 into Thingino, so high confidence, but verify.

---

## 1. Board stack

Three boards, cabled together inside the dome:

| Board | Silkscreen | Role |
|---|---|---|
| **SoC / main** | `H190_38_V1.x` (heatsink over SSC378QE) | SSC378QE + DDR + NOR; the board Thingino flashes. Console UART (ttyS0) debug pads here. |
| **Interface / IO** | (stacked on brass standoffs, board-to-board gold-finger) | Fan-out of JST connectors: sensor FPC, LED board, IR-cut, mic, speaker, AF-lens UART. |
| **PTZ base** | `HSPTZ_POE+Audio_V1.0  2023_1_9` | Pan/tilt stepper driver (ULN2803A), PTZ cal EEPROM (AT24C08), RJ45/PoE + 12 V + audio breakout, RX/TX/RST header. In the dome base. |

Lens: geared **5X optical zoom** block with **motorized zoom + focus (AF)** driven over the
AF-lens UART. Pan + tilt are **two 5-wire unipolar steppers** (`…48-4505Z`, DC 12 V) — **both
currently disconnected on the bench** (PTZ is out of scope for v1).

---

## 2. SoC GPIO map (OEM numbering — KO / 378 branch)

| GPIO | Function | Dir | Notes | Src |
|---|---|---|---|---|
| **80** | IR-CUT leg A (AOUT) | out | Day pulse = 80 high / 81 low, 250 ms, then both 0 | KO / DS |
| **81** | IR-CUT leg B (BOUT) | out | Night pulse = 81 high / 80 low, 250 ms, then both 0 | KO / DS |
| **23** | IR-detect / CDS (IR_DET) | in | Passive photocell day/night sense (1.5–12 V in) | KO / DS |
| **30** | Reset / factory button | in | Active-low (hold = factory reset w/ voice) | KO / DS |
| **54** | Speaker amp enable (SPK_EN) | out | Drive high to un-mute the external speaker amp | KO / DS |
| **33** | Alarm DI (IO input) | in | Opto DI on the extend header | KO / CFG |
| **26** | Alarm DO (IO output / Red&Blue LED) | out, =0 | Relay / alarm-light drive | KO / DS |
| **31, 32** | Core-voltage VID | out | `core_power vid_gpios=<0x1f 0x20>`, 1.0 V core — **do not touch** | DT |

IR-cut is a **2-wire H-bridge coil** (AOUT/BOUT, 5–12 V, 25–60 Ω) — plain GPIO, **not** a
serial lens-head command (unlike the JL12D2). Matches the MC-A85 exactly → Thingino `ric`
`gpio_ircut=80 gpio_ircut2=81 pulse_ms=250`. **Physical routing (PH):** the IR-cut coil plugs
into the **image-sensor board** (the filter sits at the sensor, in front of it); the gpio80/81
drive reaches it from the SoC through the **sensor FPC ribbon on the bottom of the SoC board** —
so IR-cut works whenever the sensor board + ribbon are connected (they are on the bench).

The 377/377D branch of the same `ko.sh` uses **gpio11+gpio80** (ircut) / **gpio12** (spk) /
**gpio60** (reset) — **those are NOT this board**; use the 378 numbers above.

---

## 3. PWM / LED banks (KO / DS — `pwmchip0`, period 50 µs / 20 kHz)

| Bank | PWM ch | Pad | Datasheet pin | Notes |
|---|---|---|---|---|
| **IR illuminator** | `pwm1` (PAD_PWM1) | PAD_PWM1 | LED board pin 3 = `PWM1` (IR, 0–3.3 V) | `img.conf ir_bright=100` |
| **White light** | `pwm0` (PAD_PWM0) | PAD_PWM0 | LED board pin 4 = `PWM0` (white, 0–3.3 V) | `img.conf white_bright=100` |

Runtime pad enable: `riu_w 103c 6f 0x00` + `riu_w 103c 65 0x11`. LEDs are on an **external
light board** (LED-board connector: `1=+12V 2=GND 3=PWM1/IR 4=PWM0/White`) that may or may not
be attached to the bench unit.

> White on PWM0: `infinity6c.dtsi` can route the dual-sensor frame-sync wave to PWM0
> (`vif_ds_rt_pwm_sync`). This is a single-sensor board and the OEM drives white on PWM0
> directly, so leave PWM0 as a plain LED output in the board DTS; if white strobes at the
> frame rate on first boot, move it to PWM9 as the MC-A85 did.

---

## 4. External connectors (DS — vendor connector table)

| Connector | Pin | Signal | Note |
|---|---|---|---|
| **CDS-IN** | 1 | IR_DET | CDS photocell in (passive, 1.5–12 V) → gpio23 |
| | 2 | GND | |
| **IO_OUT** | 1 | IO_OUT | Red & Blue alarm LED (3.3 V) → gpio26 |
| | 2 | GND | |
| **Power/Network** | 1 | DC 12 V+ | 9.5–15 V |
| | 2 | GND | |
| | 3–6 | RJ45_6 / RJ45_3 / RJ45_2 / RJ45_1 | 100 Mb Ethernet pairs |
| | 7 | Reset | active-low → gpio30 |
| | 8 | LED1 | Link/activity (3.3 V) |
| **Mic** | 1,2 | MIC+, MIC− | Condenser mic (analog AI) |
| **IR-CUT** | 1 | AOUT | IR-CUT+ (5–12 V, 25–60 Ω coil) → gpio80 |
| | 2 | BOUT | IR-CUT− → gpio81 |
| **Speaker** | 1,2 | SPK+, SPK− | Max 2 W |
| **LED board** | 1 | +12 V | 12 V out to light board |
| | 2 | GND | |
| | 3 | PWM1 | IR LED control (0–3.3 V) → PAD_PWM1 |
| | 4 | PWM0 | White LED control (0–3.3 V) → PAD_PWM0 |
| **Audio out** | 1 | GND | |
| | 2 | L_OUT | Line/speaker out |
| | 3 | SPK_EN | Amp enable (3.3 V) → gpio54 |
| **AF Lens** | 1 | GND | |
| | 2 | UART_TX | → SoC ttyS2 (FUART) |
| | 3 | UART_RX | ← SoC ttyS2 (FUART) |
| **Extend Board** | 1 | IOOUT | |
| | 2 | IOINPUT | |
| | 3 | SD_DET | microSD detect |
| | 4,5 | SD_D1, SD_D0 | |
| | 6 | GND | |
| | 7 | SD_CLK | |
| | 8 | GND | |
| | 9 | SD_CMD | |
| | 10,11 | SD_D3, SD_D2 | |
| | 12 | VDD 3.3 V | |
| | 13 | RESET | |
| | 14–16 | V3.3 | |

---

## 5. PTZ / motor subsystem (v2 — PH / CFG)

Two independent mechanisms:

**a) Pan + tilt** — two **5-wire unipolar stepper motors** (`…48-4505Z`, DC 12 V) driven by a
**ULN2803A** Darlington array on the PTZ base board (`HSPTZ_POE+Audio_V1.0`), silkscreen
水平电机 (pan) / 垂直电机 (tilt). 8 ULN2803A inputs ← SoC GPIOs over the inter-board cable
(step sequences bit-banged; exact GPIOs TBD — not set in `ko.sh`, driven by `nsd` at runtime).
An **AT24C08** I²C EEPROM (U3, `ATMLH519`) stores pan/tilt calibration. A base-board
**RX/TX/RST** header (near J21) breaks out serial/reset.

**b) Zoom + focus (AF lens)** — serial to the lens MCU over the **AF-lens UART**:

- Device **/dev/ttyS2** (FUART @ `0x1F220400`), **57600 8N1** (`uart.conf databit=3 parity=0
  flowctrl=0 useptz=1`). `ptz.conf protocol=0 address=1`.
- `nsd` drives zoom/focus here (`LensReset`, `StartLenStudy`/zoom-tracking cal, `nZoomPos`,
  ONVIF `AutoFocusModes AUTO/MANUAL`). **Focus is motorized** — a sharp image needs the lens
  reset + AF driven over ttyS2 (JL12D2-style `lensd`, but protocol id 0 — RE the frames by
  sniffing /dev/ttyS2 on the OEM, exact bytes are inside `nsd`).

Implication for v1: with the lens barrel still attached, the sensor streams but focus is soft
until the ttyS2 AF driver is ported. Pan/tilt (the two disconnected steppers) is fully out of
scope for v1.

---

## 6. Buses / peripherals (DT)

| Bus | Node | Addr | Use |
|---|---|---|---|
| UART0 / console | `uart0@1F221000` | — | ttyS0 115200 (console; debug pads on SoC board) |
| UART1 | `uart1@1F221200` | — | ttyS1 |
| FUART | `fuart@1F220400` | — | **ttyS2** — AF-lens @57600 |
| I²C grp0 | `i2c@1F222800` | — | 400 kHz push-pull |
| I²C grp1 | `i2c@1F222A00` | — | 400 kHz push-pull |
| I²C grp2 | `i2c@1F222C00` | — | 400 kHz push-pull |
| IMX415 sensor I²C | (one of grp0/grp1) | 7-bit **0x1A** / 8-bit 0x34 | ⚠ confirm bus + addr with `i2cdetect` on first boot |
| PWM | `@1F203200` | npwm=11 | LED banks (ch0/1), see §3 |
| SDMMC | `sstar,sdmmc`, 2 slots | — | microSD → `/dev/mmcblk1p1`, OEM mounts `/tmp/sdCard` |
| SAR ADC | `sar@1F002800` | — | present; CDS uses digital gpio23, not the ADC |
| CIR | `ir@1F007A00` | — | IR remote receiver (not the IR illuminator) |
| I²S / audio | `digmic=5 i2s-tx=6 i2s-rx=7 i2s-mck=7` | — | analog mic AI ch0 (mono/16-bit/8 kHz), AO speaker, amp-en gpio54 |

---

## 7. Flash layout (CFG / U-Boot env — identical to what Thingino must honour)

```text
nor0: 0x4F000(BOOT) 0x1000(ENV) 0x200000(KERNEL) 0xD10000(rootfs) 0xA0000(customer)
```

mtd0 BOOT (U-Boot KL_LX510) · mtd1 ENV · mtd2 KERNEL (2 MB) · mtd3 rootfs (13.69 MB, squashfs,
`root=/dev/mtdblock3`) · mtd4 customer (jffs2, `/customer`). Mem: `LX_MEM=0x10000000` (256 MB),
MMA `sz=0xa600000` (166 MB running), ~90 MB to Linux. ENV is its own partition (mtd1) → `fw_env`
on mtd1 is safe. Thingino flashes **only mtd2 + mtd3**; never mtd0/mtd1/mtd4.

---

## 8. Open items to verify live (bench, over UART)

1. **IMX415 I²C bus (grp0 vs grp1) + slave address** — `i2cdetect`; trivially flipped in the DTS padmux.
2. **IR-cut gpio80/81 polarity** — toggle and watch the filter click (expected day=80, night=81).
3. **White LED on PWM0** — confirm it does not strobe at the frame rate (frame-sync on PWM0).
4. **IMX415 mode** — Thingino runs **linear 4K** (`imx415_day.bin`); OEM ran 2-frame DOL HDR
   (`wdr_mode=3`), not replicated (i6c raptor-hal ISP does not tune DOL).
5. **AF-lens ttyS2 protocol** (v2) — sniff /dev/ttyS2 on the OEM; port a `lensd`-style driver.
6. **Pan/tilt stepper GPIOs** (v2) — identify the 8 ULN2803A-input GPIOs (monitor GPIO during OEM PTZ moves).
