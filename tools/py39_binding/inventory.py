#!/usr/bin/env python3
"""Export reproducible ELF and CPython ABI inventories for Isaac Gym bindings."""

import argparse
import hashlib
import json
import platform
import re
import shutil
import subprocess
import sys
from pathlib import Path


def run(*args):
    return subprocess.run(args, check=True, text=True, stdout=subprocess.PIPE).stdout


def sha256(path):
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def collect(binary):
    dynamic = run("readelf", "-d", str(binary))
    symbols = run("readelf", "-Ws", str(binary))
    sections = run("readelf", "-S", str(binary))
    demangled = run("nm", "-C", str(binary))

    needed = re.findall(r"\(NEEDED\).*?\[(.*?)\]", dynamic)
    init_symbols = sorted(set(re.findall(r"\bPyInit_[A-Za-z0-9_]+", symbols)))
    python_symbols = sorted(
        {
            match.group(1)
            for line in symbols.splitlines()
            if " UND " in line
            and (match := re.search(r"\b((?:_?Py)[A-Za-z0-9_]+)\b", line))
        }
    )
    wrapper_signatures = sorted(
        {
            line.strip()
            for line in demangled.splitlines()
            if "wrapInterfaceFunction<" in line
        }
    )

    return {
        "path": str(binary.resolve()),
        "size": binary.stat().st_size,
        "sha256": sha256(binary),
        "needed": needed,
        "python_init_symbols": init_symbols,
        "undefined_python_symbols": python_symbols,
        "has_debug_info": ".debug_info" in sections,
        "has_symbol_table": ".symtab" in sections,
        "wrapper_signature_count": len(wrapper_signatures),
        "wrapper_signatures": wrapper_signatures,
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("binaries", nargs="+", type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()

    missing_tools = [tool for tool in ("readelf", "nm") if shutil.which(tool) is None]
    if missing_tools:
        parser.error("missing required tools: " + ", ".join(missing_tools))

    payload = {
        "schema_version": 1,
        "host": {
            "platform": platform.platform(),
            "python": sys.version,
            "machine": platform.machine(),
            "libc": platform.libc_ver(),
        },
        "bindings": [collect(binary) for binary in args.binaries],
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, indent=2) + "\n")
    print(args.output)


if __name__ == "__main__":
    main()
