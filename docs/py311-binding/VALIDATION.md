# CPython 3.11 validation report

Date: 2026-07-15

## Environment

- CPython 3.11.15
- NumPy 2.2.6
- SciPy 1.13.1
- PyTorch 2.5.1+cpu
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

- PASS: all Python C API symbols imported by `gym_38.so` are exported by the
  tested `libpython3.11.so.1.0`
- PASS: pybind11 module initialization and type registration
- PASS: `gymapi.acquire_gym()`
- PASS: CPU PhysX, 100 steps
- PASS: GPU PhysX and GPU pipeline, 100 steps
- PASS: 20 GPU simulation create/destroy cycles, 2,000 total steps
- PASS: CPU terrain mesh, 4,608 vertices, 8,930 triangles, 100 steps
- PASS: GPU terrain mesh, 4,608 vertices, 8,930 triangles, 100 steps
- PASS: `gymtorch` JIT compilation with PyTorch 2.5.1+cpu
- PASS: zero-copy CPU tensor unwrap/wrap round-trip
- PASS: full `terrain_creation.py` bounded 20-second GPU PhysX run
- PASS: Python 3.8 original binding regression
- PASS: Python 3.9 compatibility binding regression

The full terrain command exits with status 124 because `timeout` terminates the
otherwise continuous viewer loop after 20 seconds.

## Resolved non-binding failure

The first terrain run failed because SciPy 1.14 removed `interp2d`, which
Preview 4 calls from `terrain_utils.py`. Pinning `scipy<1.14` restored the
legacy behavior; `setup.py` now encodes this upper bound.
