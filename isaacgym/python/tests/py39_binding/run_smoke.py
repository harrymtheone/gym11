#!/usr/bin/env python3
"""Bounded smoke and lifecycle tests for an Isaac Gym binding."""

import argparse
import json
import sys
import time

from isaacgym import gymapi


def check_api():
    gym = gymapi.acquire_gym()
    assert gym is not None
    vector = gymapi.Vec3(1.0, 2.0, 3.0)
    quaternion = gymapi.Quat(0.0, 0.0, 0.0, 1.0)
    assert (vector.x, vector.y, vector.z) == (1.0, 2.0, 3.0)
    assert quaternion.w == 1.0
    return gym


def create_sim(gym, use_gpu):
    params = gymapi.SimParams()
    params.up_axis = gymapi.UpAxis.UP_AXIS_Z
    params.gravity = gymapi.Vec3(0.0, 0.0, -9.81)
    params.use_gpu_pipeline = use_gpu
    params.physx.use_gpu = use_gpu
    sim = gym.create_sim(0, -1, gymapi.SIM_PHYSX, params)
    if sim is None:
        raise RuntimeError("gym.create_sim returned None")
    return sim


def exercise_lifecycle(gym, cycles, steps, use_gpu):
    for _ in range(cycles):
        sim = create_sim(gym, use_gpu)
        try:
            for _ in range(steps):
                gym.simulate(sim)
                gym.fetch_results(sim, True)
        finally:
            gym.destroy_sim(sim)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--level", choices=("api", "sim", "stress"), default="api")
    parser.add_argument("--gpu", action="store_true")
    parser.add_argument("--cycles", type=int, default=20)
    parser.add_argument("--steps", type=int, default=100)
    args = parser.parse_args()

    started = time.monotonic()
    gym = check_api()
    if args.level == "sim":
        exercise_lifecycle(gym, cycles=1, steps=args.steps, use_gpu=args.gpu)
    elif args.level == "stress":
        exercise_lifecycle(
            gym, cycles=args.cycles, steps=args.steps, use_gpu=args.gpu
        )

    print(
        json.dumps(
            {
                "status": "ok",
                "level": args.level,
                "python": sys.version,
                "gpu": args.gpu,
                "cycles": args.cycles if args.level == "stress" else 1,
                "steps": args.steps if args.level != "api" else 0,
                "elapsed_seconds": round(time.monotonic() - started, 3),
            }
        )
    )


if __name__ == "__main__":
    main()
