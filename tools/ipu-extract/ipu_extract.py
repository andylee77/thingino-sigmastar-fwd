#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""ipu_extract.py: take the detection model that thingino-ipud runs out of
firmware you already have, and stage it for a build or an SD card.

    python3 ipu_extract.py [-o OUT] [--any] [--pick MD5] [--force] INPUT...
    python3 ipu_extract.py --list INPUT...

An INPUT is a firmware image (a vendor firmware download, or a full flash read
of your own camera), a .zip holding one, a file already taken out of one, or a
folder of any of these, searched recursively. The tool finds every SquashFS in
an image, copies it to a private temporary folder, lists it with unsquashfs and
streams out only the compiled models (files that start with "SGSI"). Nothing
from an input is run.

Every model found is checked by md5 against KNOWN, the models ipud is known to
decode; any other is reported and left out, unless --any is given. OUT
(default ./ipud) then holds model.img, model.labels (the model's class names,
one comma-separated line) and an empty ipu_firmware.bin: copy them into
package/thingino-ipud/vendor/ of a firmware tree before a build, or the folder
onto a camera's SD card as ipud/.

No IPU firmware is extracted: ipud's runtime never reads the firmware file it
is given (an empty and an all-zero file run the model the same). ipud still
checks that the file exists, so the tool writes an empty one, and leaves alone
an ipu_firmware.bin already in OUT.

Needs Python 3.8 or newer and unsquashfs 4.5 or newer (squashfs-tools).
Exit status: 0 when OUT holds a model, 1 when it holds none or a file was
refused, 2 on a usage or setup error.
"""
import argparse
import hashlib
import io
import os
import re
import shutil
import struct
import subprocess
import sys
import tempfile
import zipfile
import zlib

MODEL, LABELS, FIRMWARE = 'model.img', 'model.labels', 'ipu_firmware.bin'

# The models ipud is known to decode, by md5: the size, what it is, and its
# class names (ipud reads them from model.labels, beside the model).
KNOWN = {
    'db90485e5e307daee5e04c743e91a1af': (913408,
                                         'YOLOv5 detector, 6 classes, 800x480 NV12, as JL12D2 builds ship it',
                                         'person,bicycle,car,motorcycle,bus,truck'),
}

MAX_INPUT = 512 << 20  # a larger input file is skipped: flash reads and downloads are far smaller
MAX_FILE = 64 << 20    # a larger file inside a SquashFS is not read
SUPERBLOCK = struct.Struct('<4sIIIIHHHHHHQQQQQQQQ')  # SquashFS 4.0, little-endian
LISTED = re.compile(r'^-\S*\s+\S+\s+(\d+)\s+\S+\s+\S+\s+squashfs-root(/.+)$')  # a regular file in -lls
WILDCARD = re.compile(r'[*?\[\\]')  # unsquashfs would take these as a pattern


def md5(blob):
    return hashlib.md5(blob).hexdigest()


class Found:
    """A model found in an input."""

    def __init__(self, blob, where):
        self.blob, self.where, self.md5 = blob, where, md5(blob)
        self.known = KNOWN.get(self.md5)

    def __str__(self):
        what = f'known: {self.known[1]}' if self.known else 'not on the known list'
        return f'{self.where}: model, {len(self.blob)} B, md5 {self.md5}, {what}'


def die(msg):
    print(f'ipu_extract: {msg}', file=sys.stderr)
    sys.exit(2)


def note(msg):
    print(f'note: {msg}')


def keep(found, item):
    found.append(item)
    print(item)


def find_unsquashfs(name):
    path = shutil.which(name)
    if not path:
        die(f'{name} not found. Install squashfs-tools 4.5 or newer (Debian and Ubuntu: '
            'apt install squashfs-tools; macOS: brew install squashfs; on Windows, run this tool in WSL)')
    out = subprocess.run([path, '-version'], capture_output=True, text=True, errors='replace').stdout
    m = re.search(r'version (\d+)\.(\d+)', out)
    if not m or (int(m.group(1)), int(m.group(2))) < (4, 5):
        die(f'{path} is {m.group(0) if m else "of an unknown version"}; 4.5 or newer is needed (for -cat)')
    return path


def squashfs_size(data, off):
    """The size of the SquashFS 4.0 whose superblock is at off, or 0 when the
    bytes there are not one."""
    if off + SUPERBLOCK.size > len(data):
        return 0
    (_, _, _, block_size, _, compression, block_log, _, _, major, minor, _, used,
     id_table, _, inode_table, dir_table, _, _) = SUPERBLOCK.unpack_from(data, off)
    if (major, minor) != (4, 0) or not 1 <= compression <= 6:
        return 0
    if not 12 <= block_log <= 20 or block_size != 1 << block_log:
        return 0
    if not SUPERBLOCK.size < used <= len(data) - off:
        return 0
    if not inode_table < dir_table < used or not id_table < used:
        return 0
    return used


def squashfs_images(data):
    """(offset, bytes) of each SquashFS in data."""
    found, off = [], data.find(b'hsqs')
    while off >= 0:
        size = squashfs_size(data, off)
        if size:
            found.append((off, data[off:off + size]))
        off = data.find(b'hsqs', off + max(size, 1))
    return found


def maybe_model(path, size):
    """True for a file inside a SquashFS that may be a model."""
    name = path.rsplit('/', 1)[-1]
    if not 0 < size <= MAX_FILE or WILDCARD.search(path):
        return False
    return '/dla/model/' in path or name.endswith('.img')  # kept only if it starts with SGSI


def scan_squashfs(unsquashfs, image, where, found):
    """Add the models of the SquashFS file image."""
    ls = subprocess.run([unsquashfs, '-lls', image], capture_output=True, text=True,
                        errors='replace', timeout=600)
    files = [(m.group(2), int(m.group(1))) for m in map(LISTED.match, ls.stdout.splitlines()) if m]
    if not files:
        note(f'{where}: unsquashfs listed no files ({ls.stderr.strip()[:200] or "empty"})')
        return
    for path, size in files:
        if not maybe_model(path, size):
            continue
        blob = subprocess.run([unsquashfs, '-cat', image, path.lstrip('/')], capture_output=True,
                              timeout=600).stdout
        if len(blob) != size:
            note(f'{where}:{path}: read {len(blob)} of {size} B, left out')
            continue
        if blob[:4] == b'SGSI':
            keep(found, Found(blob, f'{where}:{path}'))


def scan(unsquashfs, tmp, name, data, found):
    """Add the models that data holds: itself, or those of its SquashFS."""
    if data[:4] == b'SGSI':
        keep(found, Found(data, name))
        return
    image = os.path.join(tmp, 'squashfs.img')
    for off, fs in squashfs_images(data):
        with open(image, 'wb') as f:
            f.write(fs)
        scan_squashfs(unsquashfs, image, f'{name}@{off:#x}', found)


def unzip(name, data, depth=0):
    """(name, bytes): data itself, or the members of a zip, two levels deep."""
    if data[:4] != b'PK\x03\x04' or depth >= 2:
        yield name, data
        return
    try:
        with zipfile.ZipFile(io.BytesIO(data)) as z:
            for info in z.infolist():
                if info.is_dir():
                    continue
                if info.file_size > MAX_INPUT:
                    note(f'{name}!{info.filename}: skipped, larger than {MAX_INPUT >> 20} MB')
                    continue
                yield from unzip(f'{name}!{info.filename}', z.read(info), depth + 1)
    except (zipfile.BadZipFile, RuntimeError, NotImplementedError, OSError, EOFError, zlib.error) as e:
        note(f'{name}: not read as a zip ({e}); searched as an image')
        yield name, data


def read_inputs(paths):
    """(name, bytes) of each distinct file the inputs hold: files, the members
    of .zip files and the files of folders, recursively."""
    seen = set()
    for p in paths:
        if os.path.isdir(p):
            files = []
            for dp, dns, fns in os.walk(p):
                dns.sort()
                # a link inside an extracted rootfs points into this machine, not the image
                files += [f for f in (os.path.join(dp, fn) for fn in sorted(fns)) if not os.path.islink(f)]
        elif os.path.isfile(p):
            files = [p]
        else:
            die(f'{p}: no such file or folder')
        for f in files:
            try:
                if os.path.getsize(f) > MAX_INPUT:
                    note(f'{f}: skipped, larger than {MAX_INPUT >> 20} MB')
                    continue
                with open(f, 'rb') as fh:
                    data = fh.read()
            except OSError as e:
                note(f'{f}: not read ({e.strerror})')
                continue
            for name, blob in unzip(f, data):
                h = md5(blob)
                if blob and h not in seen:
                    seen.add(h)
                    yield name, blob


def choose(found, args):
    """The model to stage (or None), and why when none."""
    cands = {}
    for f in found:
        cands.setdefault(f.md5, f)
    if not cands:
        return None, 'none found'
    picked = [f for h, f in cands.items() if any(h.startswith(p) for p in args.pick)]
    pool = picked or [f for f in cands.values() if f.known] or list(cands.values())
    listed = ', '.join(f.md5 for f in pool)
    if not pool[0].known and not args.any:
        return None, f'refused: {len(pool)} found, none on the known list ({listed}); --any takes one'
    if len(pool) > 1:
        return None, f'refused: {len(pool)} found ({listed}); choose one with --pick MD5'
    return pool[0], ''


def holds_known_model(out):
    p = os.path.join(out, MODEL)
    if not os.path.isfile(p):
        return False
    with open(p, 'rb') as f:
        return md5(f.read()) in KNOWN


def stage(out, name, blob, force):
    """Write blob as out/name: 'written', 'same', or 'kept' when another file is
    there and force is off."""
    dst = os.path.join(out, name)
    if os.path.isfile(dst):
        with open(dst, 'rb') as f:
            if f.read() == blob:
                return 'same'
        if not force:
            return 'kept'
    with open(dst + '.part', 'wb') as f:
        f.write(blob)
    os.replace(dst + '.part', dst)
    with open(dst, 'rb') as f:
        if f.read() != blob:
            die(f'{dst} does not read back as written')
    return 'written'


def report(out):
    """Print what out holds; True when it holds a model."""
    print(f'\n{out}:')
    have = set()
    for name in (MODEL, LABELS, FIRMWARE):
        p = os.path.join(out, name)
        if not os.path.isfile(p):
            print(f'  {name:<17} missing')
            continue
        with open(p, 'rb') as f:
            blob = f.read()
        have.add(name)
        if name == LABELS:
            print(f'  {name:<17} {blob.decode("utf-8", "replace").strip()}')
        elif name == FIRMWARE:
            print(f'  {name:<17} {len(blob):>8} B  ' + ('empty: ipud checks that it exists, its runtime never '
                                                     'reads it' if not blob else 'not read by ipud\'s runtime'))
        else:
            known = KNOWN.get(md5(blob))
            what = f'known: {known[1]}' if known else 'not on the known list'
            print(f'  {name:<17} {len(blob):>8} B  md5 {md5(blob)}  {what}')
    return MODEL in have


def main():
    ap = argparse.ArgumentParser(
        description='Take the detection model thingino-ipud runs out of firmware you already have, '
                    'and stage it for a build or an SD card.')
    ap.add_argument('inputs', nargs='+', metavar='INPUT',
                    help='a firmware image or flash read, a .zip, a file taken out of one, or a folder')
    ap.add_argument('-o', '--out', default='ipud', help='the output folder (default: ./ipud)')
    ap.add_argument('--any', action='store_true', help='also take a model that is not on the known list')
    ap.add_argument('--pick', action='append', default=[], metavar='MD5',
                    help='when several are found, take this one (an md5 prefix, 6 hex digits or more); repeatable')
    ap.add_argument('--force', action='store_true', help='replace a different file already in the output folder')
    ap.add_argument('--list', action='store_true', help='only list what the inputs hold; write nothing')
    ap.add_argument('--unsquashfs', default='unsquashfs', help='the unsquashfs to run (default: the one on PATH)')
    args = ap.parse_args()
    for p in args.pick:
        if not re.fullmatch(r'[0-9a-fA-F]{6,32}', p):
            die(f'--pick {p}: give 6 to 32 hex digits of an md5')
    args.pick = [p.lower() for p in args.pick]
    unsquashfs = find_unsquashfs(args.unsquashfs)

    found, files = [], 0
    with tempfile.TemporaryDirectory(prefix='ipu_extract-') as tmp:
        for name, data in read_inputs(args.inputs):
            files += 1
            scan(unsquashfs, tmp, name, data, found)
    print(f'{files} files read, {len(found)} models found')
    if args.list:
        return 0

    os.makedirs(args.out, exist_ok=True)
    refused = False
    for p in args.pick:
        if not any(f.md5.startswith(p) for f in found):
            print(f'--pick {p}: no model found has that md5')
            refused = True
    f, why = choose(found, args)
    if not f:
        if holds_known_model(args.out):
            why += '; the known one already in the output stays'
        elif why.startswith('refused'):
            refused = True
        print(f'{MODEL}: {why}')
    else:
        dst, labels = os.path.join(args.out, MODEL), os.path.join(args.out, LABELS)
        result = stage(args.out, MODEL, f.blob, args.force)
        if result == 'kept':
            print(f'{dst}: another file is there; kept it (--force replaces it)')
            refused = True
        else:
            print(f'{dst}: {result}, from {f.where}')
            if f.known:
                result = stage(args.out, LABELS, (f.known[2] + '\n').encode(), args.force)
                if result == 'kept':
                    print(f'{labels}: another file is there; kept it (--force replaces it)')
                    refused = True
                else:
                    print(f'{labels}: {result}')
            elif os.path.isfile(labels):
                print(f'{labels}: names the classes of the model it came with; '
                      'write this model\'s classes there, or delete it')

    has_model = os.path.isfile(os.path.join(args.out, MODEL))
    firmware = os.path.join(args.out, FIRMWARE)
    if has_model and not os.path.exists(firmware):
        open(firmware, 'wb').close()
        print(f'{firmware}: written, empty (ipud checks that the file exists; its runtime never reads it)')
    elif has_model:
        print(f'{firmware}: already there, left as it is')
    report(args.out)
    if has_model:
        print('\nFor a build, copy the files into package/thingino-ipud/vendor/ of the firmware tree. '
              'For the SD card, copy the folder onto the card as ipud/, then on the camera\'s Object '
              'detection page set "Load the model from" to SD card.')
    else:
        print('\nNo model yet. The known one ships in the JL12D2\'s stock firmware: a full flash read '
              'of the camera, or its vendor firmware download.')
    return 0 if has_model and not refused else 1


if __name__ == '__main__':
    sys.exit(main())
