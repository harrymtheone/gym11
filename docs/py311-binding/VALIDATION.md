# CPython 3.11 validation report

Date: 2026-07-15

## Environment

- CPython 3.11.15
- NumPy 1.26.4
- SciPy 1.13.1
- PyTorch 2.13.0+cu132
- patchelf 0.17.2
- NVIDIA GeForce RTX 3080
- NVIDIA driver 595.71.05
- Linux x86-64, glibc 2.43

## Native artifacts

- `isaacgym/python/isaacgym/_bindings/linux-x86_64/gym_311.so`
  - SHA-256:
    `4188b07aad8799711f1d9af93aa7864457fcdb1740c1cf10a3f9cc4b5a575981`
  - exports `PyInit_gym_311`
- `isaacgym/python/isaacgym/_bindings/linux-x86_64/_gym_38_py311.so`
  - SHA-256:
    `20778f080d6e6061a4416af052a8200989d34cf5987abd0c9231c34c85580ff3`
  - needs `libpython3.11.so.1.0`
  - exports `PyInit_gym_38`

The payload hash is deterministic for the supported Preview 4 source binary.
The trampoline hash can vary with the compiler.

## Results

- PASS: Kuka bin viewer, 16 environments and 10 objects per environment
- PASS: DOF property records use the expected 40-byte item size and stride
- PASS: one-command clean rebuild and manifest/hash verification
- PASS: all Python C API symbols imported by `gym_38.so` are exported by the
  tested `libpython3.11.so.1.0`
- PASS: pybind11 module initialization and type registration
- PASS: `gymapi.acquire_gym()`
- PASS: CPU PhysX, 100 steps
- PASS: GPU PhysX and GPU pipeline, 100 steps
- PASS: 20 GPU simulation create/destroy cycles, 2,000 total steps
- PASS: CPU terrain mesh, 4,608 vertices, 8,930 triangles, 100 steps
- PASS: GPU terrain mesh, 4,608 vertices, 8,930 triangles, 100 steps
- PASS: `gymtorch` JIT compilation with PyTorch 2.13.0+cu132
- PASS: zero-copy CPU tensor unwrap/wrap round-trip
- PASS: zero-copy CUDA tensor unwrap/wrap round-trip
- PASS: GPU simulation actor root-state tensor acquisition, in-place CUDA
  modification, write-back, simulation step, and refresh
- PASS: full `terrain_creation.py` bounded 20-second GPU PhysX run
- PASS: Python 3.8 original binding regression
- PASS: Python 3.9 compatibility binding regression

The full terrain command exits with status 124 because `timeout` terminates the
otherwise continuous viewer loop after 20 seconds.

NumPy 2.2.6 is incompatible with Preview 4's bundled pybind11. It reports a
40-byte DOF property dtype with a 16-byte array stride, causing overlapping
records, invalid `hasLimits` values, and a delayed crash in
`GymGraphicsNvf::updateMeshInstanceTransform`. NumPy is therefore pinned below
version 2.

## Experimental NumPy 2 binary patch

An isolated, unsupported experiment in `tools/py311_binding/patch_numpy2.py`
shows that this specific NumPy 2.2.6 failure can be corrected without changing
the stable NumPy 1.x payload.

Ghidra and DWARF confirm the old binding reads `PyArray_Descr` using the NumPy
1.x layout:

- `elsize`: 32-bit value at `+0x20`
- legacy structured-dtype `names`: pointer at `+0x38`

The NumPy 2 layout probe places the corresponding fields at:

- `elsize`: 64-bit `npy_intp` at `+0x28`
- legacy structured-dtype `names`: pointer at `+0x68`

The experimental patch changes all three `elsize` loads and the one `names`
check. Its output SHA-256 is
`98bf725a168a0c2dee053790fec0b482ffa659517de4bd3f733b10c8febc5648`.
Under CPython 3.11.15 and NumPy 2.2.6, the patched payload passes:

- 40-byte DOF item size and 40-byte stride, with all 23 `hasLimits` values valid
- Kuka bin 16-by-10 viewer crash path for a bounded 15-second run
- CPU and GPU PhysX simulation, lifecycle stress, and terrain tests
- CPU and CUDA `gymtorch` zero-copy round trips
- GPU root-state tensor write-back and simulation

This does not change the supported configuration. The patch is tied to one
payload hash, hard-codes the NumPy 2 layout, and is not compatible with the
NumPy 1.x layout. The production dependency therefore remains `numpy<2`.

## Resolved non-binding failure

The first terrain run failed because SciPy 1.14 removed `interp2d`, which
Preview 4 called from `terrain_utils.py`. The implementation now uses
`RegularGridInterpolator`, and `setup.py` no longer needs a SciPy upper bound.

## Automated command

The complete build and CPU suite passes with:

```bash
python tools/py311_binding/run_regression.py
```

The GPU suite passes with:

```bash
python tools/py311_binding/run_regression.py --skip-build --gpu
```
