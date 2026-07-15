# Isaac Gym Preview 4 CPython 3.11 binding

This directory documents the local Linux x86-64 compatibility binding for
CPython 3.11. It is derived from the proprietary Preview 4 `gym_38.so`; the
original binary is never modified in place.

## Architecture

The generated binding consists of two files in
`isaacgym/python/isaacgym/_bindings/linux-x86_64/`:

- `gym_311.so` exports the standard `PyInit_gym_311` entry point.
- `_gym_38_py311.so` is the patched payload and retains `PyInit_gym_38`.

The trampoline loads the payload and forwards initialization. Keeping the
original payload symbol avoids invalidating its ELF GNU symbol hash table.

## Compatibility findings

The original payload directly needs `libpython3.8.so.1.0` and contains a
pybind11 runtime guard that rejects CPython 3.11. The patcher:

1. checks the original SHA-256;
2. disables only the two conditional branches into the version mismatch path;
3. uses `patchelf` to replace the longer Python SONAME with
   `libpython3.11.so.1.0`;
4. records every operation and the output hash in a JSON manifest.

No Python 3.9 type-layout patch is applied. Measured layouts are:

```text
              Python 3.8   Python 3.11
PyTypeObject       416          408
as_async           416          408
as_number          440          440
as_buffer          832          832
ht_name            848          848
ht_qualname        864          864
```

CPython 3.11 removes the 3.8 `tp_print` pointer but adds `am_send` to
`PyAsyncMethods`. The changes cancel for the fields used by pybind11 type
construction, so the Preview 4 offsets remain valid. The complete imported
Python symbol set is also present in the tested `libpython3.11.so.1.0`.

## Build

Create the target environment:

```bash
conda create -y -n isaacgym-py311 \
  python=3.11 pip "numpy<2" scipy patchelf ninja
conda activate isaacgym-py311
```

NumPy 2.x is not supported. Preview 4's bundled pybind11 produces invalid
structured-array strides with NumPy 2.x, which corrupts DOF property records
and can cause delayed native crashes.

The local `terrain_utils.py` uses `RegularGridInterpolator`, so current SciPy
versions are supported and no `<1.14` pin is required.

Build both native artifacts:

```bash
python tools/py311_binding/build_gym311.py
```

Set the runtime paths:

```bash
export PYTHONPATH="$PWD/isaacgym/python"
export LD_LIBRARY_PATH="$CONDA_PREFIX/lib:$PWD/isaacgym/python/isaacgym/_bindings/linux-x86_64${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}"
```

Verify:

```bash
python -c "from isaacgym import gymapi; print(gymapi.acquire_gym())"
```

`gymapi.py` automatically maps CPython 3.11 to `gym_311.so`; no loader override
is needed for the integrated artifact.

## One-command regression

Build the binding and run the CPU API, simulation, lifecycle stress, terrain,
and gymtorch checks:

```bash
python tools/py311_binding/run_regression.py
```

Add GPU PhysX, GPU pipeline, GPU terrain, CUDA zero-copy, and live simulation
root-state tensor write-back checks:

```bash
python tools/py311_binding/run_regression.py --gpu
```

The runner requires CPython 3.11, sets child-process Python and native library
paths automatically, validates the generated payload against its manifest,
and rejects missing build tools or an unsupported platform before testing.
Use `--skip-build` to test existing artifacts, `--skip-gymtorch` when PyTorch
is unavailable, and `--help` for stress sizing options.

## Individual tests

```bash
python isaacgym/python/tests/py39_binding/run_smoke.py \
  --require-python 3.11 --level sim --steps 100
python isaacgym/python/tests/py39_binding/run_smoke.py \
  --require-python 3.11 --level stress --gpu --cycles 20 --steps 100
python isaacgym/python/tests/py39_binding/terrain_smoke.py \
  --require-python 3.11 --gpu --steps 100
python isaacgym/python/tests/py311_binding/gymtorch_smoke.py
python isaacgym/python/tests/py311_binding/gymtorch_smoke.py \
  --cuda --simulation
timeout --signal=TERM 20s \
  python isaacgym/python/examples/terrain_creation.py --physx
```

For the last command, exit code 124 means the healthy long-running viewer was
stopped by the 20-second test timeout.

## Limitations

- The machine-code offsets and SHA gate target this exact Preview 4 binary.
- This is not a stable-ABI extension and does not imply Python 3.12 support.
- `rlgpu_311.so` is not included.
- Exception-heavy and long-duration training paths should receive additional
  stress testing before production use.
- Modified NVIDIA binaries should not be redistributed without confirming the
  applicable license terms.
