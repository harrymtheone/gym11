#!/usr/bin/env python3
"""Build the patched payload and CPython 3.9 entry-point trampoline."""

import os
import shutil
import subprocess
import sys
import sysconfig
from pathlib import Path


def main():
    if sys.version_info[:2] != (3, 9):
        raise SystemExit("build_gym39.py must run with CPython 3.9")

    root = Path(__file__).resolve().parents[2]
    tools = root / "tools" / "py39_binding"
    bindings = (
        root
        / "isaacgym"
        / "python"
        / "isaacgym"
        / "_bindings"
        / "linux-x86_64"
    )
    patcher = tools / "patch_binding.py"
    wrapper = tools / "gym39_wrapper.c"
    output = bindings / "gym_39.so"

    subprocess.run(
        [
            sys.executable,
            str(patcher),
            "gym",
            "--bindings-dir",
            str(bindings),
            "--output-dir",
            str(bindings),
            "--mode",
            "integrated",
        ],
        check=True,
    )

    compiler = os.environ.get("CC") or sysconfig.get_config_var("CC") or "cc"
    compiler = shutil.which(compiler.split()[0])
    if compiler is None:
        raise SystemExit("no C compiler was found")
    include_dir = sysconfig.get_path("include")
    subprocess.run(
        [
            compiler,
            "-shared",
            "-fPIC",
            f"-I{include_dir}",
            str(wrapper),
            "-o",
            str(output),
            "-ldl",
        ],
        check=True,
    )
    print(output)


if __name__ == "__main__":
    main()
