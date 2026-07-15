#!/usr/bin/env python3
"""Verify gymtorch zero-copy and optional GPU simulation tensor interop."""

import argparse
import json
import sys

from isaacgym import gymapi, gymtorch
import torch


def check_round_trip(device):
    source = torch.arange(12, dtype=torch.float32, device=device).reshape(3, 4)
    descriptor = gymtorch.unwrap_tensor(source)
    wrapped = gymtorch.wrap_tensor(descriptor)
    if source.data_ptr() != wrapped.data_ptr():
        raise RuntimeError(f"gymtorch copied the {device} tensor")
    if not torch.equal(source, wrapped):
        raise RuntimeError(f"gymtorch changed {device} tensor values")
    wrapped.add_(1)
    if not torch.equal(source, wrapped):
        raise RuntimeError(f"gymtorch {device} tensor does not share storage")
    return {"device": str(wrapped.device), "shape": list(wrapped.shape)}


def check_gpu_simulation(gym):
    params = gymapi.SimParams()
    params.up_axis = gymapi.UpAxis.UP_AXIS_Z
    params.gravity = gymapi.Vec3(0.0, 0.0, -9.81)
    params.physx.use_gpu = True
    params.use_gpu_pipeline = True
    sim = gym.create_sim(0, -1, gymapi.SIM_PHYSX, params)
    if sim is None:
        raise RuntimeError("gym.create_sim returned None")

    try:
        asset = gym.create_sphere(sim, 0.25, gymapi.AssetOptions())
        env = gym.create_env(
            sim,
            gymapi.Vec3(-1.0, -1.0, 0.0),
            gymapi.Vec3(1.0, 1.0, 2.0),
            1,
        )
        pose = gymapi.Transform()
        pose.p = gymapi.Vec3(0.0, 0.0, 1.0)
        gym.create_actor(env, asset, pose, "sphere", 0, 0)
        gym.prepare_sim(sim)

        descriptor = gym.acquire_actor_root_state_tensor(sim)
        states = gymtorch.wrap_tensor(descriptor)
        if states.device.type != "cuda":
            raise RuntimeError(f"root states are on {states.device}, expected CUDA")
        if tuple(states.shape) != (1, 13):
            raise RuntimeError(f"unexpected root state shape {tuple(states.shape)}")
        if states.data_ptr() != descriptor.data_address:
            raise RuntimeError("root state tensor was copied")

        gym.refresh_actor_root_state_tensor(sim)
        states[0, 0] = 2.0
        states[0, 7:13] = 0.0
        if not gym.set_actor_root_state_tensor(
            sim, gymtorch.unwrap_tensor(states)
        ):
            raise RuntimeError("set_actor_root_state_tensor failed")

        gym.simulate(sim)
        gym.fetch_results(sim, True)
        gym.refresh_actor_root_state_tensor(sim)
        torch.cuda.synchronize()
        x_position = float(states[0, 0].item())
        if abs(x_position - 2.0) > 1e-4:
            raise RuntimeError(
                f"GPU root state write-back failed: x={x_position}"
            )
        return {
            "device": str(states.device),
            "shape": list(states.shape),
            "x_after_step": x_position,
        }
    finally:
        gym.destroy_sim(sim)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--cuda", action="store_true")
    parser.add_argument("--simulation", action="store_true")
    args = parser.parse_args()
    if sys.version_info[:2] != (3, 11):
        raise RuntimeError("this smoke test requires CPython 3.11")
    if args.simulation and not args.cuda:
        parser.error("--simulation requires --cuda")
    if args.cuda and not torch.cuda.is_available():
        raise RuntimeError("CUDA PyTorch is required for --cuda")

    gym = gymapi.acquire_gym()
    if gym is None:
        raise RuntimeError("gymapi.acquire_gym returned None")

    results = [check_round_trip(torch.device("cpu"))]
    if args.cuda:
        results.append(check_round_trip(torch.device("cuda:0")))
    simulation = check_gpu_simulation(gym) if args.simulation else None
    print(
        json.dumps(
            {
                "status": "ok",
                "python": sys.version.split()[0],
                "torch": torch.__version__,
                "torch_cuda": torch.version.cuda,
                "round_trips": results,
                "simulation": simulation,
            }
        )
    )


if __name__ == "__main__":
    main()
