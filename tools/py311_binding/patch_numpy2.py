#!/usr/bin/env python3
"""Create an experimental NumPy 2 payload from the CPython 3.11 binding."""

import argparse
import hashlib
import json
import shutil
from pathlib import Path


SOURCE_SHA256 = "20778f080d6e6061a4416af052a8200989d34cf5987abd0c9231c34c85580ff3"

# Preview 4's bundled pybind11 reads PyArray_Descr::elsize as a signed
# 32-bit value at offset 0x20. NumPy 2 moved elsize to offset 0x28 and widened
# it to npy_intp. It also moved the legacy structured-dtype names pointer from
# offset 0x38 to 0x68.
NUMPY2_DESCR_LAYOUT_PATCHES = (
    (0xA00FA, b"\x48\x63\x50\x20", b"\x48\x8b\x50\x28"),
    (0x1419C4, b"\x48\x83\x78\x38\x00", b"\x48\x83\x78\x68\x00"),
    (0x141CFB, b"\x48\x63\x52\x20", b"\x48\x8b\x52\x28"),
    (0x143BCD, b"\x48\x63\x50\x20", b"\x48\x8b\x50\x28"),
)


def sha256(data):
    return hashlib.sha256(data).hexdigest()


def patch_offsets(data):
    patched = bytearray(data)
    applied = []
    for offset, expected, replacement in NUMPY2_DESCR_LAYOUT_PATCHES:
        if len(expected) != len(replacement):
            raise RuntimeError(f"NumPy 2 patch at 0x{offset:x} changes size")
        actual = bytes(patched[offset : offset + len(expected)])
        if actual != expected:
            raise RuntimeError(
                f"NumPy 2 patch mismatch at 0x{offset:x}: "
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


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--bindings-dir", required=True, type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    args = parser.parse_args()

    source = args.bindings_dir / "_gym_38_py311.so"
    wrapper = args.bindings_dir / "gym_311.so"
    if args.output_dir.resolve() == args.bindings_dir.resolve():
        parser.error("--output-dir must differ from --bindings-dir")
    original = source.read_bytes()
    source_hash = sha256(original)
    if source_hash != SOURCE_SHA256:
        parser.error(
            f"unsupported CPython 3.11 payload SHA-256 {source_hash}; "
            f"expected {SOURCE_SHA256}"
        )

    patched, applied = patch_offsets(original)
    args.output_dir.mkdir(parents=True, exist_ok=True)
    destination = args.output_dir / source.name
    destination.write_bytes(patched)
    destination.chmod(source.stat().st_mode)
    shutil.copy2(wrapper, args.output_dir / wrapper.name)

    manifest = {
        "schema_version": 1,
        "experimental": True,
        "target_python": "3.11",
        "target_numpy": "2.x",
        "source": str(source.resolve()),
        "destination": str(destination.resolve()),
        "source_sha256": source_hash,
        "output_sha256": sha256(patched),
        "patches": {"numpy2_descr_layout": applied},
    }
    destination.with_suffix(destination.suffix + ".json").write_text(
        json.dumps(manifest, indent=2) + "\n"
    )
    print(json.dumps(manifest, indent=2))


if __name__ == "__main__":
    main()
