---
jupytext:
  text_representation:
    extension: .md
    format_name: myst
    format_version: 0.13
    jupytext_version: 1.16.0
kernelspec:
  display_name: Python 3
  language: python
  name: python3
---

# 本地文件查找（旧 API）

:::{important}
本页属于**旧 API（兼容层）**文档，介绍 `reki.data_finder` 命名空间下的
接口。这些接口保持可用，旧代码无需修改；新代码请使用 `local` 数据源
（见 {ref}`data_find_local`）。新旧接口的对应关系见
{ref}`data_find_legacy_mapping`。
:::

`reki.data_finder.find_local_file()` 按内置 YAML 配置文件，在多种存储
（CMA-HPC 主存储、二级存储、CEMC 共享存储）中依次查找业务系统产品
文件，找到即返回 `pathlib.Path`，全部目录都未找到时返回 `None`。

:::{note}
本页功能依赖 CMA-HPC 的共享文件系统与业务目录结构（或挂载了相应存储
的机器，如 CMADAAS 挂载盘），**仅能在相应环境中运行**。除
`get_local_file_name()` 示例外，本页代码块不参与文档构建执行，
输出为示意。
:::

## 基本用法

```python
from reki.data_finder import find_local_file

file_path = find_local_file(
    "cma_gfs_gmf/grib2/orig",
    start_time="2023122000",
    forecast_time="3h",
)
# PosixPath('/g1/COMMONDATA/OPER/NWPC/GRAPES_GFS_GMF/Prod-grib/2023122000/ORIG/gmf.gra.2023122000003.grb2')
```

常用参数：

- `data_type`：数据类型，配置文件相对于配置根目录的路径（不含后缀），
  如 `"cma_gfs_gmf/grib2/orig"` 对应配置文件
  `{config_dir}/{data_class}/cma_gfs_gmf/grib2/orig.yaml`
- `start_time`：起报时次，字符串格式 `YYYYMMDDHH`，也接受
  `pd.Timestamp` / `datetime`
- `forecast_time`：预报时效，字符串（如 `"3h"`，由 `pd.to_timedelta`
  解析）或 `pd.Timedelta`
- `data_level`：存储级别过滤，默认 `("archive", "storage")`，见下文
- `data_class`：数据类别，选择配置子目录，默认 `"od"`（业务系统）
- `config_dir`：自定义配置根目录，默认使用 reki 内置配置
  （`reki/data_finder/conf/`）
- `obs_time`：观测资料时间（观测类 `data_type` 使用）
- `debug`：`True` 时打印模板渲染与逐级目录查找过程
- `**kwargs`：配置文件模板中声明的自定义变量（如 `storage_base`、
  `number`）

内置配置覆盖 CMA-GFS、CMA-MESO、CMA-GEPS、CMA-TYM、CMA-REPS 等业务
系统的 GRIB2 产品及中间文件，完整清单见 `reki/data_finder/conf/`
目录。配置文件格式见 {doc}`/guide/legacy_finder_config`。

## 存储级别（data_level）

配置文件的 `paths` 列表中，每个目录条目都带有 `level` 字段
（`archive` / `storage` / `runtime` 等）。`data_level` 参数过滤参与
查找的目录条目，默认 `("archive", "storage")` 即按配置顺序在归档与
二级存储中查找；传入 `None` 表示不过滤。

## CMADAAS 挂载盘与 data_class

在挂载了 CMADAAS 存储的机器上，使用 `data_class="cmadaas"` 选择
CMADAAS 配置，并用 `storage_base` 指定挂载根目录：

```python
file_path = find_local_file(
    "cma_gfs_gmf/grib2/orig",
    start_time="2026072500",
    forecast_time="24h",
    data_class="cmadaas",
    storage_base="/CMADAAS",
)
# PosixPath('/CMADAAS/DATA/NAFP/NMC/GRAPES-GFS-GLB/2026/20260725/Z_NAFP_C_BABJ_20260725000000_P_NWPC-GRAPES-GFS-GLB-02400.grib2')
```

## 集合预报成员（number）

配置文件模板中声明的自定义变量以关键字参数传入。CMA-GEPS 集合预报
需要用 `number` 指定成员编号（0 为控制预报，1–31 为集合成员）：

```python
file_path = find_local_file(
    "cma_geps/grib2/orig",
    start_time="2026072500",
    forecast_time="24h",
    number=14,
    data_class="cmadaas",
    storage_base="/CMADAAS",
)
```

## 中间文件与其他产品

`data_type` 不限于 GRIB2 产品，内置配置也包含模式输出的中间文件。
下面的示例查找 CMA-GFS 240 时效的模式面二进制文件：

```python
file_path = find_local_file(
    "cma_gfs_gmf/bin/modelvar",
    start_time="2026072500",
    forecast_time="240h",
)
```

类似的还有 `postvar`（GrADS 格式后处理文件，配套 `*_ctl` 描述文件）、
观测准备文件（`cma_gfs_gmf/obs/*`）等。

## 仅渲染文件名：get_local_file_name()

`reki.data_finder.get_local_file_name()` 只按配置渲染文件名，
**不检查文件是否存在**，因此不依赖任何数据环境：

```{code-cell} ipython3
import pandas as pd

from reki.data_finder import get_local_file_name

file_name = get_local_file_name(
    "cma_gfs_gmf/grib2/orig",
    start_time="2026081800",
    forecast_time=pd.to_timedelta("24h"),
)
file_name
```

:::{note}
`get_local_file_name()` 的 `forecast_time` 参数需要 `pd.Timedelta`
类型（不解析字符串），且不会把额外关键字参数注入模板变量——
文件名模板中使用自定义变量（如 `number`）的配置会报错。
:::

## 调试（debug=True）

传入 `debug=True` 打印渲染后的文件名与逐个尝试的目录路径，
用于排查配置或存储问题：

```python
file_path = find_local_file(
    "cma_gfs_gmf/grib2/orig",
    start_time="2026072500",
    forecast_time="24h",
    data_class="cmadaas",
    storage_base="/CMADAAS",
    debug=True,
)
```

## 多文件查找：find_local_files()

`reki.data_finder.find_local_files()` 与 `find_local_file()` 参数相近，
但按 glob 模式匹配，返回所有匹配文件的列表（无匹配时返回 `None`）：

```python
from reki.data_finder import find_local_files

file_paths = find_local_files(
    "cma_gfs_gmf/grib2/orig",
    start_time="2026072500",
    forecast_time="24h",
)
```
