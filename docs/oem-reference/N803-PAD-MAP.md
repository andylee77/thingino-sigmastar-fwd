# N803 pad and connector map

The board map of the **Anpviz / UVision N803** 5X-zoom PTZ dome (UVision module `MC800S5` / `N803`, product `Anpviz PTZIP…-5X-A 8MP`, firmware platform `N803-HS5X`), written for the Thingino profile `n803_ssc378qe_imx415` and its board device tree `infinity6c-ssc378qe-n803`. It covers the boards, the SoC's GPIOs, PWM pads, connectors and buses, and how pan, tilt, zoom and focus are driven. The head's serial protocol (Pelco-D frames and the status stream) is in the sibling doc `N803-LENS-PROTOCOL.md`.

Provenance tags per row:

- **DS**: vendor datasheet (uvision-tech / Remoteyes N803 module page and connector table).
- **KO**: OEM `/mnt/mtd/nsd/program/ko.sh`, **378 / else branch** (the active path on this board: `/sys/devices/soc0/machine` field 2 is `SSC027D-S01A`, not `SSC027A-S01A`). GPIO numbers are SigmaStar MDRV numbering.
- **DT**: decompiled OEM device tree (harvested from the unit's flash).
- **PH**: physical board inspection (bench photos 2026-10-28/29).
- **CFG**: OEM `/customer/config/setting/*.conf`.
- **CAP**: wire capture of the head link under the OEM firmware, 2026-10-29 (`N803-LENS-PROTOCOL.md`).
- **TH**: this port's N803 board files, read 2026-11-09: the board DTS (`board/sigmastar/infinity6c/patches/linux/0003-ARM-dts-infinity6c-add-the-N803-module.patch`) and the profile `configs/cameras/n803_ssc378qe_imx415/` (defconfig, kernel config fragment, `raptor.config`).
- **RUN**: seen working under Thingino on a bench unit, at the bring-up of 2026-10-31 (4K video, IR-cut, head motion) or the microSD bench test of 2026-11-06.

## Boards

Three boards are cabled together inside the dome [PH]:

| Board | Silkscreen | Role |
|---|---|---|
| **SoC / main** | `H190_38_V1.x` (heatsink over the SSC378QE) | SSC378QE, DDR and the SPI NOR; the board Thingino flashes. Console UART (ttyS0) debug pads. The sensor FPC ribbon leaves from its underside. |
| **Interface / IO** | (stacked on brass standoffs, board-to-board gold finger) | Fans out the JST connectors: sensor FPC, LED board, IR-cut, mic, speaker, head UART. |
| **PTZ base** | `HSPTZ_POE+Audio_V1.0  2023_1_9` | The head controller (an STM32), the ULN2803A stepper driver, the AT24C08 calibration EEPROM, the RJ45 / PoE, 12 V and audio breakout, and an RX/TX/RST header. In the dome base. |

The image sensor sits on its own small board at the lens block, joined to the SoC board by the sensor FPC ribbon; the IR-cut coil plugs into that board [PH].

| Part | Fact | Src |
|---|---|---|
| SoC | SigmaStar **SSC378QE** (Infinity6C), a 256 MB part. OEM DTB model `INFINITY6C SSC027D-S01A`, OEM U-Boot board tag `KL_LX510`. The Thingino board DTS includes the SSC027D reference tree and replaces its padmux. | DT / TH |
| Sensor | Sony **IMX415**, 1/2.8" 8 MP, MIPI 4-lane, MCLK 37.125 MHz. Thingino runs it in linear 4K (3840x2160) with the OEM's day tuning; the OEM ran 2-frame DOL HDR (`wdr_mode=3`), which the i6c raptor-hal ISP does not tune. | DS / TH |
| DDR | 256 MB | CFG / TH |
| Flash | 16 MB SPI NOR, five partitions | CFG / TH |
| Lens | geared 5X optical zoom block; its zoom and focus motors, like pan and tilt, take their commands from the head controller (see [PTZ drive](#ptz-drive)) | PH / CAP |

Flashing and the OEM data: Thingino writes only KERNEL (mtd2) and rootfs (mtd3), never BOOT (mtd0, the OEM U-Boot) or ENV (mtd1, the U-Boot environment, a partition of its own on this board). Its kernel names mtd4 `data` (the OEM calls it `customer`) and keeps its overlay there, so **the first flash from the OEM firmware erases mtd4**, and with it the OEM's per-unit network settings (`oemeth.conf`, which holds the unit's MAC). Read that MAC before the first flash: the profile's `S04oemmac` sets it from `/etc/default/oemmac` on the overlay [TH]. The partition offsets are in the profile's kernel config fragment (`n803_ssc378qe_imx415.kernel.config`).

## SoC GPIO

OEM numbering, from the KO 378 branch. A blank Thingino cell means the N803 profile sets nothing for that line.

| GPIO | Function | Dir | OEM behaviour | Thingino | Src |
|---|---|---|---|---|---|
| **80** | IR-cut AOUT (connector pin 1; `ko.sh` calls it IRCUT B) | out | Day: 80 high, 81 low for 250 ms, then both low | ric `gpio_ircut=80` (day), 250 ms pulse | KO / DS / TH / RUN |
| **81** | IR-cut BOUT (connector pin 2; `ko.sh` calls it IRCUT A) | out | Night: 81 high, 80 low for 250 ms, then both low | ric `gpio_ircut2=81` (night), 250 ms pulse | KO / DS / TH / RUN |
| **23** | IR detect / CDS photocell (IR_DET) | in | Passive day/night sense (1.5-12 V in) | not the day/night trigger: ric switches on image luma (`RAPTOR_IRCUT_TRIGGER="luma"`) | KO / DS / TH |
| **30** | Reset / factory button | in | Active low; hold for a factory reset with a voice prompt | | KO / DS |
| **54** | Speaker amp enable (SPK_EN) | out | High un-mutes the external speaker amp | not driven yet: the speaker path waits for the two-way audio bring-up | KO / DS / TH |
| **33** | Alarm DI (IO input) | in | Opto input on the extend header | the board DTS drops the reference tree's other microSD slot (slot 0), whose power pin is this line (`PAD_PM_GPIO9`) | KO / CFG / TH |
| **26** | Alarm DO (IO output, red and blue LED) | out, 0 | Relay / alarm-light drive | | KO / DS |
| **31, 32** | Core-voltage VID | out | `core_power vid_gpios=<0x1f 0x20>`, 1.0 V core; **do not touch** | | DT |

The IR-cut is a **2-wire H-bridge coil** (AOUT/BOUT, 5-12 V, 25-60 Ω) on plain PM GPIOs, switched through sysfs with no padmux entry; it is not a serial command as on the JL12D2. Pins and pulse are the same as on the MC-A85. ric's default pulse (10 ms) is too short for this coil, hence 250 ms [TH]. **Physical routing** [PH]: the coil plugs into the image-sensor board (the filter sits in front of the sensor), and gpio 80/81 reach it from the SoC through the sensor FPC ribbon, so the IR-cut works whenever the sensor board and its ribbon are connected. Day/night switching works under Thingino [RUN].

The 377/377D branch of the same `ko.sh` uses **gpio 11 + gpio 80** (IR-cut), **gpio 12** (speaker) and **gpio 60** (reset). **Those are not this board**; use the 378 numbers above.

## PWM and lights

The PWM controller is `pwmchip0` (`@1F203200`, npwm=11); the OEM runs both banks at a 50 µs period (20 kHz) [KO / DS / DT]. The LEDs sit on an external light board fed from the LED-board connector (1 = +12 V, 2 = GND, 3 = PWM1 / IR, 4 = PWM0 / white).

| Bank | Pad | OEM channel | Thingino channel | LED-board pin | OEM setting | Src |
|---|---|---|---|---|---|---|
| **IR illuminator** (850 nm) | `PAD_PWM1` | PWM1 | PWM1 (`PINMUX_FOR_PWM1_MODE_1`) | 3 (0-3.3 V) | `img.conf ir_bright=100` | KO / DS / TH |
| **White light** | `PAD_PWM0` | PWM0 | **PWM9** (`PINMUX_FOR_PWM9_MODE_2`) | 4 (0-3.3 V) | `img.conf white_bright=100` | KO / DS / TH |

**Why white is PWM9 under Thingino** [TH]: `infinity6c.dtsi` enables the dual-sensor frame-sync wave on PWM0 (`vif_ds_rt_pwm_sync = <1>`, pin 0), which `mi.ko` drives. With PWM0 on `PAD_PWM0` that wave would reach the white bank and strobe it at the frame rate, as on the MC-A85; moving white to PWM9 is the fix the MC-A85 needed. PWM9 on the same pad does not depend on `mi.ko` leaving PWM0 alone, and PWM0 is routed to no pad, so the wave drives nothing. The OEM drives white on PWM0 directly and enables the pads at run time with `riu_w 103c 6f 0x00` and `riu_w 103c 65 0x11` [KO].

Under Thingino [TH], `S30light` sets both channels up at boot from `/etc/default/light`; `/usr/sbin/light` switches a bank on or off (`light ir on`, `light white off`) and sets its brightness (`light ir brightness 0-100`), and the WebUI light buttons use it. ric switches the IR bank with day/night through `RAPTOR_IRCUT_IRLED_CMD="/usr/sbin/light ir"`.

The Ethernet link and activity LEDs are `PAD_PM_LED0` and `PAD_PM_LED1`, muxed as `PINMUX_FOR_LED0_MODE_1` and `PINMUX_FOR_LED1_MODE_1` [TH]; the Power/Network connector's pin 8 (LED1) is the link/activity output [DS].

## Connectors

The vendor connector table [DS], with the SoC line each pin reaches:

| Connector | Pin | Signal | Note |
|---|---|---|---|
| **CDS-IN** | 1 | IR_DET | CDS photocell in (passive, 1.5-12 V) → gpio 23 |
| | 2 | GND | |
| **IO_OUT** | 1 | IO_OUT | Red and blue alarm LED (3.3 V) → gpio 26 |
| | 2 | GND | |
| **Power/Network** | 1 | DC 12 V+ | 9.5-15 V |
| | 2 | GND | |
| | 3-6 | RJ45_6 / RJ45_3 / RJ45_2 / RJ45_1 | 100 Mb Ethernet pairs |
| | 7 | Reset | active low → gpio 30 |
| | 8 | LED1 | Link/activity (3.3 V) |
| **Mic** | 1, 2 | MIC+, MIC− | Condenser mic (analog AI) |
| **IR-CUT** | 1 | AOUT | IR-CUT+ (5-12 V, 25-60 Ω coil) → gpio 80 |
| | 2 | BOUT | IR-CUT− → gpio 81 |
| **Speaker** | 1, 2 | SPK+, SPK− | Max 2 W |
| **LED board** | 1 | +12 V | 12 V out to the light board |
| | 2 | GND | |
| | 3 | PWM1 | IR LED control (0-3.3 V) → `PAD_PWM1` |
| | 4 | PWM0 | White LED control (0-3.3 V) → `PAD_PWM0` |
| **Audio out** | 1 | GND | |
| | 2 | L_OUT | Line/speaker out |
| | 3 | SPK_EN | Amp enable (3.3 V) → gpio 54 |
| **AF Lens** | 1 | GND | |
| | 2 | UART_TX | → SoC ttyS2 (FUART) |
| | 3 | UART_RX | ← SoC ttyS2 (FUART) |
| **Extend Board** | 1 | IOOUT | |
| | 2 | IOINPUT | |
| | 3 | SD_DET | microSD detect |
| | 4, 5 | SD_D1, SD_D0 | |
| | 6 | GND | |
| | 7 | SD_CLK | |
| | 8 | GND | |
| | 9 | SD_CMD | |
| | 10, 11 | SD_D3, SD_D2 | |
| | 12 | VDD 3.3 V | |
| | 13 | RESET | |
| | 14-16 | V3.3 | |

"AF Lens" is the datasheet's name for the ttyS2 connector. In this dome ttyS2 is the Pelco-D link to the head controller on the PTZ base, which runs zoom and focus as well as pan and tilt (see [PTZ drive](#ptz-drive)) [CAP].

## Buses

| Bus | Node | Pads in the Thingino DTS | Use | Src |
|---|---|---|---|---|
| UART0 / console | `uart0@1F221000` | | ttyS0 115200; debug pads on the SoC board | DT |
| UART1 | `uart1@1F221200` | | ttyS1 | DT |
| FUART | `fuart@1F220400` | `PAD_FUART_RX`, `PAD_FUART_TX` (2-wire) | **ttyS2**: the head link, Pelco-D at 57600 8N1 | DT / TH / CAP |
| I²C group 0 | `i2c@1F222800` | | 400 kHz push-pull | DT |
| I²C group 1 | `i2c@1F222A00` | `PAD_I2C1_SCL`, `PAD_I2C1_SDA` | 400 kHz push-pull; the IMX415 (adapter 1) | DT / TH |
| I²C group 2 | `i2c@1F222C00` | | 400 kHz push-pull | DT |
| IMX415 sensor | on I²C group 1 | | 7-bit **0x1A** (8-bit 0x34); the 4K stream runs on this setting | TH / RUN |
| PWM | `@1F203200`, npwm=11 | `PAD_PWM0` (as PWM9), `PAD_PWM1` (PWM1) | the light banks (see [PWM and lights](#pwm-and-lights)) | DT / TH |
| SDMMC | `sstar,sdmmc` | `PAD_SD_CLK`, `PAD_SD_CMD`, `PAD_SD_D0`-`D3`; detect `PAD_PM_SD_CDZ` (0x16); power `PAD_FUART_RTS` (0x2d, GPIO mode) | the extend-board microSD slot | DT / TH / RUN |
| Ethernet | `emac0` (base tree) | | the i6c internal EMAC and its internal MII PHY, 100 Mb; the RJ45 routes through the PTZ base board to the SoC board | TH / DS |
| SAR ADC | `sar@1F002800` | | present; the CDS input uses digital gpio 23, not the ADC | DT |
| CIR | `ir@1F007A00` | | IR remote receiver (not the IR illuminator) | DT |
| I²S / audio | `digmic=5 i2s-tx=6 i2s-rx=7 i2s-mck=7` | | analog mic on AI device 0 (mono, 16-bit, 8 kHz); AO to the speaker amp (enable gpio 54) | DT / TH |

**microSD.** The OEM tree keeps the SSC027D evaluation board's two slots [DT]; the OEM firmware mounts the card at `/tmp/sdCard` (`/dev/mmcblk1p1`). This board wires one: the OEM tree's slot 1, SDIO IP 1 on the `PAD_SD_*` pads. The Thingino DTS keeps only that slot (`slotnum = <1>`, `slot-ip-orders = <1 1 2>`), because the reference tree's slot 0 (IP 0 on the `PAD_SD1_IO` pads, detect `PAD_SD1_IO6`, power `PAD_PM_GPIO9`) would take gpio 33, the alarm input, as its power pin [TH]. `FUART_RTS` is free for the SD power because the head link runs 2-wire. On a bench unit a card was detected at boot, mounted at `/mnt/mmcblk0p1` by the mdev automount, read and written, and came back after a reboot and a power cycle (2026-11-06) [RUN].

## PTZ drive

**The SoC does not drive the motors.** One controller on the PTZ base board, an **STM32**, takes every motion command, pan, tilt, zoom and focus, as **Pelco-D** frames (address 1) on **ttyS2** (FUART at `0x1F220400`, 57600 8N1), and streams its status back on the same line [CAP]. The SoC sends only Pelco-D and drives no motor GPIO: the Thingino board DTS muxes no motor pins [TH] and the head moves under Thingino [RUN].

| Part | Where | What | Src |
|---|---|---|---|
| STM32 head controller | PTZ base board (`HSPTZ_POE+Audio_V1.0`) | takes Pelco-D from the SoC, drives the motors, streams a status frame with the zoom and focus encoder positions | CAP |
| ULN2803A Darlington array | PTZ base board | the stepper driver for pan and tilt, fed by the STM32 | CAP / PH |
| Pan and tilt motors | dome | two 5-wire unipolar steppers (`…48-4505Z`, DC 12 V), silkscreen 水平电机 (pan) / 垂直电机 (tilt) | PH |
| AT24C08 EEPROM (U3, `ATMLH519`) | PTZ base board | pan/tilt calibration | PH / CAP |
| RX/TX/RST header | PTZ base board, near J21 | serial and reset breakout | PH |
| Zoom and focus motors | lens block | moved by the Pelco-D zoom in/out and focus near/far commands | CAP |

**OEM** [CFG / CAP]: the OEM daemon `nsd` writes the frames. `uart.conf` sets `devname=/dev/ttyS2`, `buadrate=57600` (sic), `databit=3`, `parity=0`, `flowctrl=0`, `useptz=1`; `ptz.conf` sets `protocol=0` (Pelco-D) and `address=1`.

**Thingino** [TH / RUN]: `lensd` runs in its Pelco-only mode (`BR2_PACKAGE_THINGINO_LENSD_MODE_PELCO=y`, started as `lensd -P`) and writes the same Pelco-D on ttyS2. ONVIF PTZ and the WebUI PTZ buttons reach it through `/run/lensd.cmd`. The head file `hs5x` (`package/thingino-lensd/files/heads/hs5x.conf`) holds the head's measured motion, which ONVIF RelativeMove needs. The head moves on `lensd` commands under Thingino (zoom and focus at the 2026-10-31 bring-up, pan in the 2026-11-06 bench test).

The Pelco-D frame table, the status-stream decode and the capture method are in `N803-LENS-PROTOCOL.md`.

An earlier version of this map had the SoC bit-banging the eight ULN2803A inputs from GPIOs under `nsd`, with pan and tilt out of scope. The 2026-10-29 capture showed that the STM32 drives the steppers and the SoC only sends Pelco-D.
