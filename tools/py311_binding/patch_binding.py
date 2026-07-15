#!/usr/bin/env python3
"""Create an experimental CPython 3.11 payload from Preview 4 gym_38.so."""

import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
from pathlib import Path


SOURCE_SHA256 = "447166f3a11439b39c71284f9ba6c3a40e34e29a9f556f549469a439ff2717a5"

# The pybind11 entry point compares Py_GetVersion() with the compile-time
# "3.8" string and rejects a two-digit minor version even when the prefix
# matches. NOP only the two conditional jumps into the ImportError path.
VERSION_GUARD_PATCHES = (
    (0x76D54, b"\x0f\x85\xbe\x00\x00\x00", b"\x90" * 6),
    (0x76D64, b"\x0f\x86\xae\x00\x00\x00", b"\x90" * 6),
)

# CPython 3.11 removes the 3.8 tp_print field (-8 bytes) but adds am_send to
# PyAsyncMethods (+8 bytes). Fields from as_number through ht_qualname return
# to their 3.8 offsets. This table remains separate so any empirically proven
# 3.11-only correction is byte-guarded rather than inherited from py39.
GYM_PY311_TYPE_LAYOUT_PATCHES = ()


def digest(data):
    return hashlib.sha256(data).hexdigest()


def patch_offsets(data, patches, category):
    patched = bytearray(data)
    applied = []
    for offset, expected, replacement in patches:
        actual = bytes(patched[offset : offset + len(expected)])
        if actual != expected:
            raise RuntimeError(
                f"{category} patch mismatch at 0x{offset:x}: "
                f"expected {expected.hex()}, found {actual.hex()}"
            )
        if len(expected) != len(replacement):
            raise RuntimeError(f"{category} patch at 0x{offset:x} changes size")
        patched[offset : offset + len(expected)] = replacement
        applied.append(
            {
                "offset": f"0x{offset:x}",
                "before": expected.hex(),
                "after": replacement.hex(),
            }
        )
    return bytes(patched), applied


def command_output(*args):
    return subprocess.run(
        args, check=True, text=True, stdout=subprocess.PIPE
    ).stdout


def verify(path):
    dynamic = command_output("readelf", "-d", str(path))
    symbols = command_output("readelf", "-Ws", str(path))
    needed = re.findall(r"\(NEEDED\).*?\[(.*?)\]", dynamic)
    if "libpython3.11.so.1.0" not in needed:
        raise RuntimeError("payload does not depend on libpython3.11.so.1.0")
    if "libpython3.8.so.1.0" in needed:
        raise RuntimeError("payload still depends on libpython3.8.so.1.0")
    if "PyInit_gym_38" not in symbols:
        raise RuntimeError("payload does not export PyInit_gym_38")
    return {"needed": needed, "python_init": "PyInit_gym_38"}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--bindings-dir", required=True, type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    parser.add_argument(
        "--mode", choices=("prototype", "integrated"), default="prototype"
    )
    parser.add_argument("--patchelf", default=os.environ.get("PATCHELF", "patchelf"))
    args = parser.parse_args()

    patchelf = shutil.which(args.patchelf)
    if patchelf is None:
        parser.error("patchelf is required for the longer Python 3.11 SONAME")

    source = args.bindings_dir / "gym_38.so"
    output_name = (
        "gym_38.so" if args.mode == "prototype" else "_gym_38_py311.so"
    )
    destination = args.output_dir / output_name
    original = source.read_bytes()
    source_hash = digest(original)
    if source_hash != SOURCE_SHA256:
        parser.error(
            f"unsupported gym_38.so SHA-256 {source_hash}; "
            f"expected {SOURCE_SHA256}"
        )

    patched, version_patches = patch_offsets(
        original, VERSION_GUARD_PATCHES, "version guard"
    )
    patched, layout_patches = patch_offsets(
        patched, GYM_PY311_TYPE_LAYOUT_PATCHES, "type layout"
    )

    args.output_dir.mkdir(parents=True, exist_ok=True)
    destination.write_bytes(patched)
    destination.chmod(source.stat().st_mode)
    subprocess.run(
        [
            patchelf,
            "--replace-needed",
            "libpython3.8.so.1.0",
            "libpython3.11.so.1.0",
            str(destination),
        ],
        check=True,
    )
    verification = verify(destination)
    output = destination.read_bytes()

    manifest = {
        "schema_version": 1,
        "experimental": True,
        "target_python": "3.11",
        "mode": args.mode,
        "source": str(source.resolve()),
        "destination": str(destination.resolve()),
        "source_sha256": source_hash,
        "output_sha256": digest(output),
        "patches": {
            "version_guard": version_patches,
            "cpython311_type_layout": layout_patches,
            "needed": {
                "before": "libpython3.8.so.1.0",
                "after": "libpython3.11.so.1.0",
            },
        },
        "verification": verification,
    }
    manifest_path = destination.with_suffix(destination.suffix + ".json")
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n")
    print(json.dumps(manifest, indent=2))


if __name__ == "__main__":
    main()
