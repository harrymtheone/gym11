# Isaac Gym CPython 3.9 binding experiment

This directory records a local compatibility experiment for the proprietary
Isaac Gym Preview 4 binaries. It does not contain or redistribute NVIDIA
binaries. Generated binaries live under `build/py39-binding/`.

## Baseline

- Host: Linux x86_64, glibc 2.43
- GPU: NVIDIA GeForce RTX 3080
- Driver: 595.71.05
- Reference runtime: CPython 3.8.20
- Target runtime: CPython 3.9.23
- Original modules contain DWARF debug information and are not stripped.
- `gym_38.so` directly requires `libpython3.8.so.1.0`.
- The complete asset bundle is now available under `isaacgym/assets/`.

`baseline_inventory.json` is generated with:

```bash
python3 tools/py39_binding/inventory.py \
  isaacgym/python/isaacgym/_bindings/linux-x86_64/gym_38.so \
  isaacgym/python/isaacgym/_bindings/linux-x86_64/rlgpu_38.so \
  --output docs/py39-binding/baseline_inventory.json
```

## Generate an experimental binding

The patcher never edits the original module. The prototype changes only the
same-length ELF dependency string from CPython 3.8 to 3.9:

```bash
python3 tools/py39_binding/patch_binding.py gym \
  --bindings-dir isaacgym/python/isaacgym/_bindings/linux-x86_64 \
  --output-dir build/py39-binding/prototype \
  --mode prototype
```

Load it explicitly:

```bash
export PYTHONPATH="$PWD/isaacgym/python"
export LD_LIBRARY_PATH="$CONDA_PREFIX/lib:$PWD/isaacgym/python/isaacgym/_bindings/linux-x86_64"
export ISAACGYM_GYM_BINDING="$PWD/build/py39-binding/prototype/gym_38.so"
python -c 'from isaacgym import gymapi; print(gymapi.acquire_gym())'
```

The discovered incompatibility is the CPython 3.9 removal of the trailing
`PyTypeObject.tp_print` field. That moved the subsequent `PyHeapTypeObject`
members by eight bytes. The patcher validates and adjusts the affected
instructions in the bundled pybind11 code.

Build the integrated pair with a Python 3.9 interpreter. The verified commands
for the current nested SDK layout are in
[`MIGRATION_GUIDE_CN.md`](MIGRATION_GUIDE_CN.md), section 5.

This creates:

- `gym_39.so`: a small standard CPython entry-point trampoline exporting
  `PyInit_gym_39`.
- `_gym_38_py39.so`: the patched binding payload. It retains
  `PyInit_gym_38`, avoiding invalidation of the ELF GNU symbol hash table.

Both files must remain in the bindings directory. The normal `gymapi.py`
version selection then loads `gym_39.so` without an environment override.

## Validation

Run `python/tests/py39_binding/run_smoke.py --level api` first. Higher levels
create a simulation and terrain mesh. `terrain_smoke.py` is bounded and
headless; the original `terrain_creation.py` still needs an asset bundle and a
display.

Validated on the baseline machine:

- CPython 3.8 reference import and CPU simulation
- CPython 3.9 API import and `acquire_gym`
- CPU and GPU PhysX simulation
- 20 GPU create/destroy cycles and 2,000 simulation steps
- asset-free terrain mesh with 4,608 vertices and 8,930 triangles
- `gymtorch` JIT build and zero-copy CPU tensor round-trip with PyTorch 2.5.1

The full `terrain_creation.py` now resolves its asset and ran for the bounded
20-second validation window without an error or crash.

## RL GPU follow-up

`rlgpu_38.so` uses the same pybind11 and CPython layouts, but has its own
instruction offsets and requires a separate `_rlgpu_38_py39.so` payload plus
`rlgpu_39.so` trampoline. Its implementation should follow the same sequence:
extract and validate all `PyHeapTypeObject` accesses, patch only those
instructions, then test import before running an RL task. It is intentionally
not treated as part of the terrain milestone.

These binaries use CPython private symbols and were not built for the stable
ABI. Passing imports is not enough: repeated lifecycle and long-step tests are
required before treating the experiment as usable.
