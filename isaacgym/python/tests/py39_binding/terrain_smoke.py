#!/usr/bin/env python3
"""Headless, asset-free terrain mesh smoke test for the native binding."""

import argparse
import json
import sys
import time

import numpy as np

from isaacgym import gymapi
from isaacgym.terrain_utils import (
    SubTerrain,
    convert_heightfield_to_trimesh,
    random_uniform_terrain,
    sloped_terrain,
)


def build_terrain():
    horizontal_scale = 0.25
    vertical_scale = 0.005
    rows = 48
    columns = 48
    heightfield = np.zeros((rows * 2, columns), dtype=np.int16)

    def subterrain():
        return SubTerrain(
            width=rows,
            length=columns,
            vertical_scale=vertical_scale,
            horizontal_scale=horizontal_scale,
        )

    heightfield[:rows, :] = random_uniform_terrain(
        subterrain(),
        min_height=-0.2,
        max_height=0.2,
        step=0.2,
        downsampled_scale=0.5,
    ).height_field_raw
    heightfield[rows:, :] = sloped_terrain(
        subterrain(), slope=-0.5
    ).height_field_raw
    return convert_heightfield_to_trimesh(
        heightfield,
        horizontal_scale=horizontal_scale,
        vertical_scale=vertical_scale,
        slope_threshold=1.5,
    )


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--steps", type=int, default=100)
    parser.add_argument("--gpu", action="store_true")
    parser.add_argument("--require-python")
    args = parser.parse_args()
    active_python = f"{sys.version_info.major}.{sys.version_info.minor}"
    if args.require_python and args.require_python != active_python:
        parser.error(
            f"requires Python {args.require_python}, running {active_python}"
        )

    started = time.monotonic()
    gym = gymapi.acquire_gym()
    params = gymapi.SimParams()
    params.up_axis = gymapi.UpAxis.UP_AXIS_Z
    params.gravity = gymapi.Vec3(0.0, 0.0, -9.81)
    params.physx.use_gpu = args.gpu
    params.use_gpu_pipeline = args.gpu
    sim = gym.create_sim(0, -1, gymapi.SIM_PHYSX, params)
    if sim is None:
        raise RuntimeError("gym.create_sim returned None")

    try:
        vertices, triangles = build_terrain()
        mesh = gymapi.TriangleMeshParams()
        mesh.nb_vertices = vertices.shape[0]
        mesh.nb_triangles = triangles.shape[0]
        gym.add_triangle_mesh(sim, vertices.flatten(), triangles.flatten(), mesh)
        for _ in range(args.steps):
            gym.simulate(sim)
            gym.fetch_results(sim, True)
    finally:
        gym.destroy_sim(sim)

    print(
        json.dumps(
            {
                "status": "ok",
                "vertices": int(vertices.shape[0]),
                "triangles": int(triangles.shape[0]),
                "steps": args.steps,
                "gpu": args.gpu,
                "elapsed_seconds": round(time.monotonic() - started, 3),
            }
        )
    )


if __name__ == "__main__":
    main()
