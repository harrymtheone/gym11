#!/usr/bin/env python3
"""Build and regression-test the Isaac Gym CPython 3.11 binding."""

import argparse
import hashlib
import json
import os
import platform
import shutil
import subprocess
import sys
import time
from pathlib import Path


def sha256(path):
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def require(condition, message):
    if not condition:
        raise SystemExit(f"preflight failed: {message}")


def child_environment(root, bindings):
    environment = os.environ.copy()
    python_path = str(root / "isaacgym" / "python")
    library_paths = [str(Path(sys.prefix) / "lib"), str(bindings)]
    if environment.get("PYTHONPATH"):
        python_path += os.pathsep + environment["PYTHONPATH"]
    if environment.get("LD_LIBRARY_PATH"):
        library_paths.append(environment["LD_LIBRARY_PATH"])
    environment["PYTHONPATH"] = python_path
    environment["LD_LIBRARY_PATH"] = os.pathsep.join(library_paths)
    return environment


def run_case(name, command, environment, root):
    print(f"\n==> {name}", flush=True)
    started = time.monotonic()
    completed = subprocess.run(command, cwd=root, env=environment)
    elapsed = round(time.monotonic() - started, 3)
    if completed.returncode != 0:
        raise RuntimeError(
            f"{name} failed with exit code {completed.returncode}: "
            f"{' '.join(map(str, command))}"
        )
    return {"name": name, "status": "passed", "elapsed_seconds": elapsed}


def verify_artifacts(bindings):
    wrapper = bindings / "gym_311.so"
    payload = bindings / "_gym_38_py311.so"
    manifest_path = payload.with_suffix(payload.suffix + ".json")
    for path in (wrapper, payload, manifest_path):
        require(path.is_file(), f"missing generated artifact: {path}")

    manifest = json.loads(manifest_path.read_text())
    require(manifest.get("target_python") == "3.11", "manifest target is not 3.11")
    require(
        manifest.get("output_sha256") == sha256(payload),
        "payload hash does not match its manifest",
    )
    require(
        manifest.get("verification", {}).get("python_init") == "PyInit_gym_38",
        "payload initialization symbol was not verified",
    )
    return {
        "wrapper": str(wrapper),
        "wrapper_sha256": sha256(wrapper),
        "payload": str(payload),
        "payload_sha256": sha256(payload),
    }


def main():
    parser = argparse.ArgumentParser(
        description="Build and test the Isaac Gym CPython 3.11 binding."
    )
    parser.add_argument("--skip-build", action="store_true")
    parser.add_argument("--gpu", action="store_true", help="add GPU PhysX tests")
    parser.add_argument("--skip-gymtorch", action="store_true")
    parser.add_argument("--steps", type=int, default=100)
    parser.add_argument("--stress-cycles", type=int, default=20)
    args = parser.parse_args()

    require(sys.version_info[:2] == (3, 11), "CPython 3.11 is required")
    require(sys.platform.startswith("linux"), "Linux is required")
    require(platform.machine() in ("x86_64", "AMD64"), "x86-64 is required")
    require(args.steps > 0, "--steps must be positive")
    require(args.stress_cycles > 0, "--stress-cycles must be positive")

    root = Path(__file__).resolve().parents[2]
    bindings = (
        root
        / "isaacgym"
        / "python"
        / "isaacgym"
        / "_bindings"
        / "linux-x86_64"
    )
    source = bindings / "gym_38.so"
    require(source.is_file(), f"missing Preview 4 source binding: {source}")
    for executable in ("readelf",):
        require(shutil.which(executable) is not None, f"{executable} is required")
    if not args.skip_build:
        require(shutil.which("patchelf") is not None, "patchelf is required")
        require(
            shutil.which((os.environ.get("CC") or "cc").split()[0]) is not None,
            "a C compiler is required",
        )

    environment = child_environment(root, bindings)
    results = []
    started = time.monotonic()

    if not args.skip_build:
        results.append(
            run_case(
                "build binding",
                [sys.executable, str(root / "tools/py311_binding/build_gym311.py")],
                environment,
                root,
            )
        )

    artifacts = verify_artifacts(bindings)
    smoke = root / "isaacgym/python/tests/py39_binding/run_smoke.py"
    terrain = root / "isaacgym/python/tests/py39_binding/terrain_smoke.py"
    common = [sys.executable, str(smoke), "--require-python", "3.11"]

    results.append(run_case("API import", common + ["--level", "api"], environment, root))
    results.append(
        run_case(
            "CPU simulation",
            common + ["--level", "sim", "--steps", str(args.steps)],
            environment,
            root,
        )
    )
    results.append(
        run_case(
            "CPU lifecycle stress",
            common
            + [
                "--level",
                "stress",
                "--cycles",
                str(args.stress_cycles),
                "--steps",
                str(args.steps),
            ],
            environment,
            root,
        )
    )
    results.append(
        run_case(
            "CPU terrain",
            [
                sys.executable,
                str(terrain),
                "--require-python",
                "3.11",
                "--steps",
                str(args.steps),
            ],
            environment,
            root,
        )
    )

    if args.gpu:
        results.append(
            run_case(
                "GPU simulation",
                common + ["--level", "sim", "--gpu", "--steps", str(args.steps)],
                environment,
                root,
            )
        )
        results.append(
            run_case(
                "GPU lifecycle stress",
                common
                + [
                    "--level",
                    "stress",
                    "--gpu",
                    "--cycles",
                    str(args.stress_cycles),
                    "--steps",
                    str(args.steps),
                ],
                environment,
                root,
            )
        )
        results.append(
            run_case(
                "GPU terrain",
                [
                    sys.executable,
                    str(terrain),
                    "--require-python",
                    "3.11",
                    "--gpu",
                    "--steps",
                    str(args.steps),
                ],
                environment,
                root,
            )
        )

    if not args.skip_gymtorch:
        results.append(
            run_case(
                "gymtorch zero-copy",
                [
                    sys.executable,
                    str(
                        root
                        / "isaacgym/python/tests/py311_binding/gymtorch_smoke.py"
                    ),
                ],
                environment,
                root,
            )
        )

    print(
        "\n"
        + json.dumps(
            {
                "status": "passed",
                "python": sys.version.split()[0],
                "gpu_tests": args.gpu,
                "artifacts": artifacts,
                "tests": results,
                "elapsed_seconds": round(time.monotonic() - started, 3),
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
