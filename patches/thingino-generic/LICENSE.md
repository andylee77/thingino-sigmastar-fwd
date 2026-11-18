# License of the generic patch series

These patches apply to [Thingino](https://github.com/themactep/thingino-firmware)
(MIT), on top of the series in [`../thingino-sigmastar/`](../thingino-sigmastar/).
Every file they touch is Thingino's own: the raptor agent adapter and
`agent-lib`, web UI pages and scripts, a CGI, a web UI manifest and a package
makefile. They carry no patch to another project and no vendor file.

| Path inside a patch | Modifies | License |
|---|---|---|
| everything: `package/thingino-agent/`, `package/thingino-raptor/files/`, `package/thingino-raptor/thingino-raptor.mk`, `package/thingino-ipud/files/` | Thingino | MIT ([`LICENSE`](../../LICENSE)) |

A file's own license statement wins over this table.
