#!/usr/bin/env python3
"""Build the patched payload and CPython 3.11 entry-point trampoline."""

import os
import shutil
import subprocess
import sys
import sysconfig
from pathlib import Path


def main():
    if sys.version_info[:2] != (3, 11):
        raise SystemExit("build_gym311.py must run with CPython 3.11")

    root = Path(__file__).resolve().parents[2]
    tools = root / "tools" / "py311_binding"
    bindings = (
        root
        / "isaacgym"
        / "python"
        / "isaacgym"
        / "_bindings"
        / "linux-x86_64"
    )
    output = bindings / "gym_311.so"

    subprocess.run(
        [
            sys.executable,
            str(tools / "patch_binding.py"),
            "--bindings-dir",
            str(bindings),
            "--output-dir",
            str(bindings),
            "--mode",
            "integrated",
        ],
        check=True,
    )

    compiler_setting = os.environ.get("CC") or sysconfig.get_config_var("CC") or "cc"
    compiler = shutil.which(compiler_setting.split()[0])
    if compiler is None:
        raise SystemExit("no C compiler was found")
    subprocess.run(
        [
            compiler,
            "-shared",
            "-fPIC",
            f"-I{sysconfig.get_path('include')}",
            str(tools / "gym311_wrapper.c"),
            "-o",
            str(output),
            "-ldl",
        ],
        check=True,
    )

    symbols = subprocess.run(
        ["readelf", "-Ws", str(output)],
        check=True,
        text=True,
        stdout=subprocess.PIPE,
    ).stdout
    if "PyInit_gym_311" not in symbols:
        raise RuntimeError("gym_311.so does not export PyInit_gym_311")
    print(output)


if __name__ == "__main__":
    main()
