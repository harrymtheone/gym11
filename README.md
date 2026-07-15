# Isaac Gym Preview 4（本地兼容版）

本仓库基于 NVIDIA Isaac Gym Preview 4 SDK，并在保留原始功能的基础上，
增加了 CPython 3.9/3.11 兼容绑定、自动化回归测试以及新版本 SciPy 的适配。

> Isaac Gym Preview 4 已停止公开维护，核心模拟器与原生绑定属于 NVIDIA
> 专有软件。本仓库中的兼容修改不代表 NVIDIA 官方支持。

## 主要改动

- 支持在 Linux x86-64 上使用 CPython 3.11 加载 `gymapi`。
- 使用独立 trampoline 加载修补后的原生 payload，不修改
`PyInit_gym_38` 符号。
- 提供 CPython 3.9 兼容实验及中文迁移文档。
- 将 NumPy 正式支持范围限制为 `<2`，避免结构化数组 ABI 不兼容导致的
内存破坏。
- 使用 `RegularGridInterpolator` 替代已被 SciPy 删除的 `interp2d`。
- 增加 CPU/GPU PhysX、terrain、生命周期以及 `gymtorch` 回归测试。
- 提供独立的 NumPy 2.x 二进制补丁实验和 Ghidra 审计脚本；该实验不属于
正式支持配置。

## 环境要求

- Linux x86-64
- NVIDIA GPU 和可用的 NVIDIA 驱动
- NumPy 1.x
- PyTorch (已测试 2.13.0+cu132)
- `patchelf`、C 编译器 （运行不需要，仅开发使用）



## 安装

在仓库根目录执行：

```bash
conda create -y -n isaacgym-py311 python=3.11
conda activate isaacgym-py311
```

安装合适的 PyTorch

```bash
pip3 install torch torchvision --index-url https://download.pytorch.org/whl/cu132
```

然后安装Isaac Gym Python 包：

```bash
python -m pip install -e isaacgym/python
```

仓库已包含生成好的 CPython 3.11 绑定，普通安装不需要编译。

### 设置运行时路径：

```bash
export PYTHONPATH="$PWD/isaacgym/python${PYTHONPATH:+:$PYTHONPATH}"
export LD_LIBRARY_PATH="$CONDA_PREFIX/lib:$PWD/isaacgym/python/isaacgym/_bindings/linux-x86_64${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}"
```

建议将这两个变量写入 Conda 环境的激活脚本，而不是设置为全局系统变量。

## 快速验证

验证绑定导入：

```bash
python -c "from isaacgym import gymapi; print(gymapi.acquire_gym())"
```

运行示例时应从示例目录启动，以保证相对资源路径正确：

```bash
cd isaacgym/python/examples
python joint_monkey.py
```



### 开发与重新编译

只有修改原生绑定或需要重新生成 CPython 3.11 绑定时，才需要安装
`patchelf` 和 C 编译器：

```bash
conda install -y -c conda-forge patchelf
python tools/py311_binding/build_gym311.py
```



## 回归测试

构建绑定并运行 CPU 测试：

```bash
python tools/py311_binding/run_regression.py
```

运行完整 GPU PhysX、CUDA tensor 和 GPU terrain 测试：

```bash
python tools/py311_binding/run_regression.py --gpu
```

仅测试已有绑定时可添加 `--skip-build`。

## NumPy 兼容性

正式环境必须使用：

```text
numpy<2
```

Preview 4 内置的旧版 pybind11 按 NumPy 1.x 的 `PyArray_Descr` 布局读取
字段。在 NumPy 2.x 下，DOF 属性可能出现 `itemsize=40`、`stride=16`，
导致记录重叠、数据损坏和延迟的原生崩溃。

`tools/py311_binding/patch_numpy2.py` 是针对 NumPy 2.2.6 的独立研究实验。
它绑定到特定 payload 哈希，不能与 NumPy 1.x 共用，也不应替代正式的
`numpy<2` 配置。

### NumPy 2 实验用法

建议创建独立环境，避免影响正式的 NumPy 1.x 环境：

```bash
conda create -y -n isaacgym-py311-numpy2 python=3.11 pip numpy=2.2.6
conda activate isaacgym-py311-numpy2
```

按照本机 CUDA 环境安装 PyTorch 和 torchvision，然后安装 Isaac Gym 及其余 Python
依赖。由于 `setup.py` 的正式依赖范围是 `numpy<2`，实验环境需要使用
`--no-deps`：

```bash
python -m pip install -e isaacgym/python --no-deps
python -m pip install scipy pyyaml pillow imageio ninja
```

从仓库内已有的 CPython 3.11 payload 生成独立 NumPy 2 payload：

```bash
python tools/py311_binding/patch_numpy2.py \
  --bindings-dir isaacgym/python/isaacgym/_bindings/linux-x86_64 \
  --output-dir build/py311-numpy2
```

不要将 `--output-dir` 指向正式 bindings 目录。补丁工具会拒绝原地覆盖，
以免破坏 NumPy 1.x payload。

选择实验绑定并设置运行时路径：

```bash
export PYTHONPATH="$PWD/isaacgym/python${PYTHONPATH:+:$PYTHONPATH}"
export LD_LIBRARY_PATH="$CONDA_PREFIX/lib:$PWD/isaacgym/python/isaacgym/_bindings/linux-x86_64${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}"
export ISAACGYM_GYM_BINDING="$PWD/build/py311-numpy2/gym_311.so"
```

验证 NumPy 版本与绑定导入：

```bash
python -c "import numpy; from isaacgym import gymapi; print(numpy.__version__, gymapi.acquire_gym())"
```

可以从示例目录执行 Kuka 场景，覆盖曾经出现结构化 DOF 数组损坏的路径：

```bash
cd isaacgym/python/examples
python kuka_bin.py
```

结束实验或切回正式 NumPy 1.x 环境时，清除绑定覆盖：

```bash
unset ISAACGYM_GYM_BINDING
```

## 目录结构

```text
isaacgym/                         NVIDIA Preview 4 SDK、资源和 Python 包
docs/py311-binding/              CPython 3.11 设计与验证记录
docs/py39-binding/               CPython 3.9 实验和迁移文档
tools/py311_binding/             3.11 构建、补丁和回归工具
tools/py39_binding/              3.9 二进制分析与补丁工具
```

## 已知限制

- 只验证了 Linux x86-64。
- CPython 3.11 绑定不是稳定 ABI 扩展，不代表支持 Python 3.12。
- 未提供 `rlgpu_311.so`。
- NumPy 2.x 补丁仍属于实验性质。
- 长时间训练、异常处理和不同驱动版本仍需在目标机器上单独验证。
- 分发修改后的 NVIDIA 二进制前，请确认原 SDK 许可证允许相应行为。

## 进一步阅读

- 原始离线文档：`isaacgym/docs/index.html`
- CPython 3.11 使用说明：`docs/py311-binding/README.md`
- CPython 3.11 验证报告：`docs/py311-binding/VALIDATION.md`
- CPython 3.9 中文迁移指南：
`docs/py39-binding/MIGRATION_GUIDE_CN.md`

