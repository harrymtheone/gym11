#!/usr/bin/env python3
"""Compile gymtorch and verify a zero-copy CPU tensor round-trip."""

import json
import sys

from isaacgym import gymapi, gymtorch
import torch


def main():
    if sys.version_info[:2] != (3, 11):
        raise RuntimeError("this smoke test requires CPython 3.11")
    if gymapi.acquire_gym() is None:
        raise RuntimeError("gymapi.acquire_gym returned None")

    source = torch.arange(12, dtype=torch.float32).reshape(3, 4)
    descriptor = gymtorch.unwrap_tensor(source)
    wrapped = gymtorch.wrap_tensor(descriptor)
    if source.data_ptr() != wrapped.data_ptr():
        raise RuntimeError("gymtorch round-trip copied the tensor")
    if not torch.equal(source, wrapped):
        raise RuntimeError("gymtorch round-trip changed tensor values")
    print(
        json.dumps(
            {
                "status": "ok",
                "python": sys.version.split()[0],
                "torch": torch.__version__,
                "shape": list(wrapped.shape),
            }
        )
    )


if __name__ == "__main__":
    main()
