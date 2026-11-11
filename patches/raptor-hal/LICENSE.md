# Licenses of the raptor-hal patch series

These patches apply to [gtxaspec/raptor-hal](https://github.com/gtxaspec/raptor-hal),
whose repository `LICENSE` is GPL-3.0 and whose files carry their own SPDX
lines. Each hunk keeps the license of the file it creates or modifies:

| Files | License |
|---|---|
| `src/infinity6c/**`: John Chia's Infinity6C backend, imported verbatim, and our changes to it | GPL-3.0-or-later, as its files state ([text](../../LICENSES/GPL-3.0.txt)) |
| `sigmastar-headers/**`: John Chia's reconstructed SigmaStar MI ABI headers | per file: MIT where the file is vendored from OpenIPC divinus (its "Copyright (c) 2024 OpenIPC" notice stays), GPL-3.0-or-later where the file says so |
| files that state `SPDX-License-Identifier: MIT` (gtxaspec's `src/*.c`, the SigmaStar glue `src/caps_sigmastar.inc` and `src/hal_internal_sigmastar.h`) | MIT |
| files with no statement (`Makefile`, `mk/sigmastar.mk`, `FORK.md`, tests) | GPL-3.0, the repository's |

The HAL calls SigmaStar's proprietary MI libraries at run time. Those
libraries are not part of this series and carry no license from it.
