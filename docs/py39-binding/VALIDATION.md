# Validation report

Date: 2026-07-15

## Environment

- CPython reference: 3.8.20
- CPython target: 3.9.23
- GPU: NVIDIA GeForce RTX 3080
- Driver: 595.71.05
- Host glibc: 2.43

## Results

- PASS: original `gym_38.so` import and API smoke on CPython 3.8
- PASS: original binding CPU PhysX simulation on CPython 3.8
- PASS: `gym_39.so` natural loader import and `acquire_gym`
- PASS: CPython 3.9 CPU PhysX simulation
- PASS: CPython 3.9 GPU PhysX and GPU pipeline simulation
- PASS: 20 GPU simulation create/destroy cycles, 100 steps each
- PASS: headless terrain mesh, 4,608 vertices, 8,930 triangles, 100 GPU steps
- PASS: `gymtorch` JIT compilation with PyTorch 2.5.1+cpu
- PASS: zero-copy CPU tensor unwrap/wrap round-trip
- PASS: full `isaacgym/python/examples/terrain_creation.py` resolved
  `isaacgym/assets/urdf/ball.urdf` and ran for the 20-second validation window
  on `DISPLAY=:0` without an error or crash

## Generated artifacts

- `isaacgym/python/isaacgym/_bindings/linux-x86_64/gym_39.so`
  - SHA-256: `47b6e3018c4b07d9b2d6028044444162c3519faff69a090027caf29c96af9a52`
- `isaacgym/python/isaacgym/_bindings/linux-x86_64/_gym_38_py39.so`
  - SHA-256: `75cec9f8b42fdcbf5e687c815113b16d167a25f08b339c8489f7d7050b4a8f74`

The payload hash is deterministic for the identified Isaac Gym Preview 4
source binary. The trampoline hash may vary with the host compiler.
