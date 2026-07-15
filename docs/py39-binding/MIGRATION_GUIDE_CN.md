# Isaac Gym Preview 4 迁移至 Python 3.9

本文记录将 Isaac Gym Preview 4 的 Linux Python binding 从 CPython 3.8
迁移到 CPython 3.9 时遇到的问题、最终方案、构建方法和验证结果。

## 1. 当前目录结构

本文中的命令均从项目根目录执行：

```text
isaacgym/
├── isaacgym/
│   ├── assets/
│   └── python/
│       ├── examples/
│       ├── isaacgym/
│       │   └── _bindings/linux-x86_64/
│       └── setup.py
├── tools/py39_binding/
└── docs/py39-binding/
```

目标文件为：

```text
isaacgym/python/isaacgym/_bindings/linux-x86_64/gym_39.so
isaacgym/python/isaacgym/_bindings/linux-x86_64/_gym_38_py39.so
```

两个文件必须放在同一目录中。

## 2. 原始加载机制

`gymapi.py` 根据当前解释器版本生成模块名：

```text
Python 3.6 -> gym_36.so
Python 3.7 -> gym_37.so
Python 3.8 -> gym_38.so
Python 3.9 -> gym_39.so
```

原始发行包没有 `gym_39.so`，并且 `setup.py` 将版本限制为
`python_requires='>=3.6,<3.9'`，因此 Python 3.9 无法直接使用。

底层 PhysX、Carbonite 和 CUDA plugin 本身不直接依赖 Python minor
版本。版本耦合主要位于 pybind11 binding 层。

## 3. 遇到的问题

### 3.1 ELF 直接依赖 Python 3.8

`gym_38.so` 的动态依赖包含：

```text
libpython3.8.so.1.0
```

Python 3.9 环境无法解析该依赖。由于新旧字符串长度相同，实验 binding
将其替换为：

```text
libpython3.9.so.1.0
```

### 3.2 pybind11 主动拒绝 Python 3.9

模块入口中包含编译版本检查。只修改 ELF 依赖后，导入会报告：

```text
Python version mismatch: module was compiled for Python 3.8
```

因此还需要将模块内的运行时版本常量由 `3.8` 改为 `3.9`。

### 3.3 绕过版本检查后发生段错误

解除版本检查后，模块在注册第一个 pybind11 enum 时崩溃。GDB 回溯显示
崩溃位置为 CPython 的 `type_qualname()`，调用方是 pybind11
`make_new_python_type()`。

根因是 CPython 3.9 删除了 `PyTypeObject` 末尾的 `tp_print` 指针。
这使 `PyTypeObject` 缩小 8 字节，并导致后续 `PyHeapTypeObject` 字段全部
前移 8 字节。旧 binding 仍按 Python 3.8 的偏移写入 `ht_name`、
`ht_qualname`、buffer methods 等字段，造成类型对象损坏。

`tools/py39_binding/patch_binding.py` 对已确认的机器指令执行窄补丁：

```text
Python 3.8 heap type offset -> Python 3.9 heap type offset
0x340 -> 0x338
0x348 -> 0x340
0x350 -> 0x348
0x360 -> 0x358
```

每个补丁都先检查原始字节。若输入不是当前已验证的 Preview 4
`gym_38.so`，脚本会停止，而不是盲目修改其他二进制。

### 3.4 直接重命名 `PyInit_gym_38` 无效

将 ELF 字符串中的 `gym_38` 全部替换为 `gym_39` 后，`readelf` 虽然能看到
`PyInit_gym_39`，动态加载器仍报告：

```text
dynamic module does not define module export function (PyInit_gym_39)
```

原因是 ELF `.gnu.hash` 中仍保存旧符号的哈希值。仅替换字符串不会重建
动态符号哈希表。

最终没有继续修改原二进制的符号表，而是采用双文件方案：

- `_gym_38_py39.so`：修复后的主体，保留 `PyInit_gym_38`。
- `gym_39.so`：使用 Python 3.9 编译的小型 trampoline，导出
  `PyInit_gym_39`，加载主体并调用 `PyInit_gym_38`。

### 3.5 Conda 环境找不到 `libpython3.9.so`

Conda 环境包含 `libpython3.9.so.1.0`，但其目录不一定自动进入动态加载器
搜索路径。运行前需要设置：

```bash
export LD_LIBRARY_PATH="$CONDA_PREFIX/lib:$PWD/isaacgym/python/isaacgym/_bindings/linux-x86_64${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}"
```

### 3.6 文件结构和资源问题

最初只有 Python 子目录，完整 `terrain_creation.py` 缺少
`assets/urdf/ball.urdf`，且没有确认显示环境。当前结构已经补全：

```text
isaacgym/assets/urdf/ball.urdf
DISPLAY=:0
```

示例使用 `__file__` 计算资源路径，因此目前能够正确找到该文件。

## 4. 环境准备

已验证的环境：

```text
Linux x86_64
CPython 3.9.23
NVIDIA GeForce RTX 3080
NVIDIA driver 595.71.05
glibc 2.43
```

创建环境：

```bash
conda create -y -n isaacgym-py39 python=3.9 pip
conda activate isaacgym-py39
conda install -y numpy scipy
python -m pip install ninja
```

安装项目时，`setup.py` 的 `python_requires` 应为：

```python
python_requires='>=3.6,<3.10'
```

本地安装：

```bash
python -m pip install --no-deps -e isaacgym/python
```

`--no-deps` 用于避免自动下载体积很大的最新 CUDA PyTorch。其他依赖应按
实际用途单独安装。

## 5. 重新生成 binding

先生成修复后的 payload：

```bash
python tools/py39_binding/patch_binding.py gym \
  --bindings-dir isaacgym/python/isaacgym/_bindings/linux-x86_64 \
  --output-dir isaacgym/python/isaacgym/_bindings/linux-x86_64 \
  --mode integrated
```

再用 Python 3.9 头文件编译 trampoline：

```bash
cc -shared -fPIC \
  $("$CONDA_PREFIX/bin/python3.9-config" --includes) \
  tools/py39_binding/gym39_wrapper.c \
  -o isaacgym/python/isaacgym/_bindings/linux-x86_64/gym_39.so \
  -ldl
```

检查结果：

```bash
readelf -Ws \
  isaacgym/python/isaacgym/_bindings/linux-x86_64/gym_39.so \
  | rg PyInit_gym_39

readelf -d \
  isaacgym/python/isaacgym/_bindings/linux-x86_64/_gym_38_py39.so \
  | rg libpython3.9.so.1.0
```

## 6. 运行方法

激活环境并设置路径：

```bash
conda activate isaacgym-py39
export PYTHONPATH="$PWD/isaacgym/python"
export LD_LIBRARY_PATH="$CONDA_PREFIX/lib:$PWD/isaacgym/python/isaacgym/_bindings/linux-x86_64${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}"
```

验证导入：

```bash
python -c "from isaacgym import gymapi; print(gymapi.acquire_gym())"
```

运行完整 terrain 示例：

```bash
python isaacgym/python/examples/terrain_creation.py --physx
```

该示例创建 viewer 并持续运行，需手动关闭窗口。自动测试可使用：

```bash
timeout --signal=TERM 20s \
  python isaacgym/python/examples/terrain_creation.py --physx
```

退出码 `124` 表示程序在 20 秒后被 `timeout` 主动终止，不表示仿真失败。

## 7. 验证结果

以下项目已经通过：

- Python 3.8 原始 binding 导入和 CPU PhysX 基线。
- Python 3.9 `gym_39.so` 正常自动加载。
- `gymapi.acquire_gym()`。
- CPU PhysX。
- GPU PhysX 和 GPU pipeline。
- 20 次 GPU sim 创建/销毁，共 2,000 个仿真 step。
- 无资源 terrain mesh：4,608 vertices、8,930 triangles。
- `gymtorch` 在 Python 3.9、PyTorch 2.5.1+cpu 下 JIT 编译。
- CPU tensor 的零拷贝 unwrap/wrap。
- 完整 `terrain_creation.py` 使用其 800 个环境配置启动，并连续运行
  20 秒无报错或崩溃。

完整示例的测试输出包含：

```text
+++ Using GPU PhysX
Physics Engine: PhysX
Physics Device: cuda:0
GPU Pipeline: disabled
```

这里的 `GPU Pipeline: disabled` 是示例没有把
`args.use_gpu_pipeline` 写入 `SimParams` 导致的，不代表 PhysX 没有使用
GPU；输出已经明确显示 Physics Device 为 `cuda:0`。

## 8. 限制与风险

- 当前机器码偏移仅针对这一份 Isaac Gym Preview 4 `gym_38.so`。
- 这不是 CPython Stable ABI binding，只支持已测试的 CPython 3.9。
- 导入成功不等价于所有 Gym API 都已经覆盖；长时间训练仍需额外压力测试。
- `rlgpu_38.so` 有独立的机器码偏移，目前尚未生成 `rlgpu_39.so`。
- `gym_39.so` 和 `_gym_38_py39.so` 必须配套部署。
- NVIDIA 原始文件采用专有许可。修改后的二进制默认仅用于本地研究，不应
  在未确认许可条件的情况下重新分发。

## 9. 后续迁移建议

1. 为 `rlgpu_38.so` 单独提取和验证所有 `PyHeapTypeObject` 偏移。
2. 生成 `_rlgpu_38_py39.so` 和对应的 `rlgpu_39.so` trampoline。
3. 使用实际 RL 任务验证 tensor、生命周期和长时间训练稳定性。
4. 为生成脚本增加原始 binary SHA-256 白名单，进一步避免误补丁。
5. 若升级到 Python 3.10 或更高版本，应重新分析 CPython 对象布局，不能
   直接复用本迁移补丁。
