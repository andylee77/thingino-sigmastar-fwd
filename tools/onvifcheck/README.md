# onvifcheck

An ONVIF conformance and client-compatibility checker for IP cameras. It runs
about 90 tests over the device, media (Media and Media2), PTZ, imaging, events
and DeviceIO services, validates each answer against the ONVIF schemas, and
shows what the clients make of it: the parse of onvif-zeep-async 4.0.4, the
version Frigate 0.17 ships, and replays of what Frigate, Home Assistant and
go2rtc ask for. It was written while bringing ONVIF up on Thingino cameras
and works against any ONVIF camera.

## Install

Python 3.11 (what it was written with):

```sh
python3 -m venv .venv
. .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

`requirements.txt` pins onvif-zeep-async 4.0.4, inside Frigate 0.17's
`4.0.*`, so the zeep view is Frigate's parse. Pillow is optional: it serves
the snapshot luminance check of `X-IMG-EFFECT`. The ONVIF schemas download
from github.com/onvif/specs on the first run that validates, into
`%LOCALAPPDATA%\onvifcheck` or `~/.cache/onvifcheck`; `--fetch-schemas`
downloads them again.

## Run

```sh
export ONVIF_USER=<user> ONVIF_PASS=<password>
python onvifcheck.py --list                         # the tests; no camera needed
python onvifcheck.py <camera-ip>                    # every read-only test
python onvifcheck.py <camera-ip> --client frigate   # what Frigate relies on
python onvifcheck.py <camera-ip> --suite ptz --allow-move --mac <mac-tail>
python onvifcheck.py <camera-ip> -o results/        # write the run to a folder
python onvifcheck.py --discover                     # WS-Discovery probe
```

- **Credentials:** `-u` and `-p`, or `ONVIF_USER` and `ONVIF_PASS`; none is
  built in. Prefer the variables, since a shell keeps its history; the
  results record the command line with the password masked.
- **Safe by default:** only queries and temporary event subscriptions run.
  Opt in to more:
  - `--allow-move`: PTZ and focus moves, each matched or returned (GotoHome
    and GotoPreset leave the head there);
  - `--allow-config`: `Set*` calls (imaging, relays), each restored after;
  - `--allow-preset-write`: SetPreset and RemovePreset (a head may keep
    positions in slots it does not list).
- **The MAC gate:** opt-in tests run only when the camera's MAC, read over
  ONVIF, matches `--mac` or the fleet entry, so a wrong address cannot move
  the wrong head.
- **Selecting tests:** `--suite` takes services
  (`device,discovery,media,media2,ptz,imaging,events,deviceio,clients`),
  `--only` and `--skip` take test-ID globs, and `--client frigate|ha|go2rtc`
  runs the tests that client depends on.
- **Schema checks:** an XSD error warns by default; `--strict-schema` makes
  it fail, and `--no-schema` skips validation and the zeep view.
- **A fleet file**, optional: `--fleet FILE` or `ONVIFCHECK_FLEET`, JSON as
  `{"units": {"<name>": {"mac": "<mac>", "last_ip": "<ip>"}}}`. The target can
  then be a unit's name or the tail of its MAC.
- **Exit code:** 1 when any test fails or errors.

## Results

`-o DIR` writes `results.json`, `results.csv`, `summary.md` and `trace/`, one
XML file per SOAP exchange with its request and reply. Keep them private:
they hold the camera's MAC and address, the user name and WS-Security digests
(the password element is blanked), and the replies as received, which can
include a snapshot URI that carries an API key.

## Test IDs

Test IDs follow the ONVIF device test specifications
(github.com/onvif/testspecs) where one applies. The `X-*` tests are the
tool's own: client behaviour Frigate and Home Assistant rely on, and checks
that a setting the camera accepts actually takes effect.

## License

MIT, as the rest of this repository.
