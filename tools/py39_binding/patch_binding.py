#!/usr/bin/env python3
"""Create an experimental CPython 3.9 Isaac Gym binding from a 3.8 binary."""

import argparse
import hashlib
import json
import re
import subprocess
from pathlib import Path


MODULES = {
    "gym": {
        "source": "gym_38.so",
        "prototype": "gym_38.so",
        "integrated": "_gym_38_py39.so",
    },
    "rlgpu": {
        "source": "rlgpu_38.so",
        "prototype": "rlgpu_38.so",
        "integrated": "_rlgpu_38_py39.so",
    },
}

# CPython 3.9 removed the trailing ``tp_print`` pointer from PyTypeObject.
# Consequently, every PyHeapTypeObject member after ``ht_type`` moved by
# eight bytes. Isaac Gym's bundled pybind11 writes these fields directly.
# These offsets are validated against the unmodified Preview 4 gym_38.so
# before being changed.
GYM_PY39_TYPE_LAYOUT_PATCHES = (
    (0xA1CA2, b"\x48\x89\x83\x50\x03\x00\x00", b"\x48\x89\x83\x48\x03\x00\x00"),
    (0xA1CB0, b"\x48\x89\x83\x60\x03\x00\x00", b"\x48\x89\x83\x58\x03\x00\x00"),
    (0xA1D80, b"\x48\xc7\x83\x50\x03\x00\x00", b"\x48\xc7\x83\x48\x03\x00\x00"),
    (0xA2E2D, b"\x48\x89\x85\x50\x03\x00\x00", b"\x48\x89\x85\x48\x03\x00\x00"),
    (0xA2E3B, b"\x48\x89\x85\x60\x03\x00\x00", b"\x48\x89\x85\x58\x03\x00\x00"),
    (0xA2F0E, b"\x48\x89\x85\x50\x03\x00\x00", b"\x48\x89\x85\x48\x03\x00\x00"),
    (0xA2F1C, b"\x48\x89\x85\x60\x03\x00\x00", b"\x48\x89\x85\x58\x03\x00\x00"),
    (0xA30C0, b"\x48\xc7\x85\x50\x03\x00\x00", b"\x48\xc7\x85\x48\x03\x00\x00"),
    (0xA30D0, b"\x48\xc7\x85\x50\x03\x00\x00", b"\x48\xc7\x85\x48\x03\x00\x00"),
    (0xA43CA, b"\x49\x89\x87\x50\x03\x00\x00", b"\x49\x89\x87\x48\x03\x00\x00"),
    (0xA43DF, b"\x49\x89\x87\x60\x03\x00\x00", b"\x49\x89\x87\x58\x03\x00\x00"),
    (0xA44C8, b"\x49\x8d\x87\x40\x03\x00\x00", b"\x49\x8d\x87\x38\x03\x00\x00"),
    (0xA44DD, b"\x49\x89\x87\x40\x03\x00\x00", b"\x49\x89\x87\x38\x03\x00\x00"),
    (0xA44EB, b"\x49\x89\x87\x48\x03\x00\x00", b"\x49\x89\x87\x40\x03\x00\x00"),
)


def sha256(data):
    return hashlib.sha256(data).hexdigest()


def replace_exact(data, old, new, description):
    if len(old) != len(new):
        raise ValueError(f"{description}: replacements must have equal length")
    count = data.count(old)
    if count == 0:
        raise RuntimeError(f"{description}: {old!r} was not found")
    return data.replace(old, new), count


def patch_offsets(data, patches):
    patched = bytearray(data)
    applied = []
    for offset, expected, replacement in patches:
        actual = bytes(patched[offset : offset + len(expected)])
        if actual != expected:
            raise RuntimeError(
                f"layout patch mismatch at 0x{offset:x}: "
                f"expected {expected.hex()}, found {actual.hex()}"
            )
        patched[offset : offset + len(expected)] = replacement
        applied.append(
            {
                "offset": f"0x{offset:x}",
                "before": expected.hex(),
                "after": replacement.hex(),
            }
        )
    return bytes(patched), applied


def verify(path, module, mode):
    dynamic = subprocess.run(
        ["readelf", "-d", str(path)], check=True, text=True, stdout=subprocess.PIPE
    ).stdout
    symbols = subprocess.run(
        ["readelf", "-Ws", str(path)], check=True, text=True, stdout=subprocess.PIPE
    ).stdout
    needed = re.findall(r"\(NEEDED\).*?\[(.*?)\]", dynamic)
    expected_init = f"PyInit_{module}_38"
    if "libpython3.9.so.1.0" not in needed:
        raise RuntimeError("patched binary does not depend on libpython3.9.so.1.0")
    if expected_init not in symbols:
        raise RuntimeError(f"patched binary does not export {expected_init}")
    return {"needed": needed, "python_init": expected_init}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("module", choices=sorted(MODULES))
    parser.add_argument("--bindings-dir", required=True, type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    parser.add_argument(
        "--mode",
        choices=("prototype", "integrated"),
        default="prototype",
        help="integrated produces the payload consumed by the _39 trampoline",
    )
    args = parser.parse_args()

    config = MODULES[args.module]
    source = args.bindings_dir / config["source"]
    destination = args.output_dir / config[args.mode]
    if not source.is_file():
        parser.error(f"source binding does not exist: {source}")

    original = source.read_bytes()
    patched, python_replacements = replace_exact(
        original,
        b"libpython3.8.so.1.0",
        b"libpython3.9.so.1.0",
        "CPython dependency",
    )
    patched, version_replacements = replace_exact(
        patched,
        b"3.8\x00",
        b"3.9\x00",
        "pybind11 runtime version check",
    )
    layout_patches = []
    if args.module == "gym":
        patched, layout_patches = patch_offsets(
            patched, GYM_PY39_TYPE_LAYOUT_PATCHES
        )
    module_replacements = 0

    args.output_dir.mkdir(parents=True, exist_ok=True)
    destination.write_bytes(patched)
    destination.chmod(source.stat().st_mode)
    verification = verify(destination, args.module, args.mode)

    manifest = {
        "schema_version": 1,
        "experimental": True,
        "module": args.module,
        "mode": args.mode,
        "source": str(source.resolve()),
        "destination": str(destination.resolve()),
        "source_sha256": sha256(original),
        "output_sha256": sha256(patched),
        "replacements": {
            "libpython3.8_to_3.9": python_replacements,
            "runtime_version_3.8_to_3.9": version_replacements,
            "module_38_to_39": module_replacements,
            "cpython39_type_layout": layout_patches,
        },
        "verification": verification,
    }
    manifest_path = destination.with_suffix(destination.suffix + ".json")
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n")
    print(json.dumps(manifest, indent=2))


if __name__ == "__main__":
    main()
