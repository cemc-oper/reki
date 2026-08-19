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

# GRIB 数据加载（旧 API）

:::{important}
本页属于**旧 API（兼容层）**文档，介绍 `reki.format.grib` 命名空间下的
接口。这些接口保持可用，旧代码无需修改；新代码请使用新 API
（`from_source()` / `sel()` / `to_xarray()`），见
{doc}`/guide/data_load`、{doc}`/guide/grib_parameter`、
{doc}`/guide/grib_level`。新旧接口的对应关系见
{ref}`data_find_legacy_mapping`。
:::

`reki.format.grib.load_field_from_file()` 从 GRIB 文件中加载**单个**
要素场，返回 `xarray.DataArray`（未找到时返回 `None`）。常用参数：

- `file_path`：GRIB 文件路径
- `parameter`：要素名（字符串或 GRIB 键字典）
- `level_type`：层次类型（字符串或 GRIB 键字典）
- `level`：层次值
- `engine`：解码引擎，`"eccodes"`（默认）或 `"cfgrib"`
- `**kwargs`：任意 GRIB 键作为附加筛选条件

本页示例使用内置 `test` 数据源的 **ecmwf_ifs** 冻结数据集
（说明见 {doc}`/getting-started/test-data`）。下面的代码单元仅用
新 API 取得缓存文件路径，本页其余代码均为旧 API 写法，
除标注外均可执行：

```{code-cell} ipython3
from reki import from_source

file_path = from_source("test", "ecmwf_ifs").mutate().path
print(file_path)
```

## 基本用法

加载 850 hPa 温度场：

```{code-cell} ipython3
from reki.format.grib import load_field_from_file

field = load_field_from_file(
    file_path,
    parameter="t",
    level_type="pl",
    level=850,
)
float(field.mean())
```

同名函数也可以从引擎子模块导入
（`reki.format.grib.eccodes.load_field_from_file`），参数相同。

## 要素名（parameter）

`parameter` 支持三类字符串名称（ecCodes `shortName`、WGRIB2 要素名、
CEMC 要素名）和字典形式的 GRIB 键。名称解析顺序与背景介绍见新 API 文档
{doc}`/guide/grib_parameter`，本页只给出旧 API 的写法示例。

### ecCodes shortName

```{code-cell} ipython3
t2m = load_field_from_file(
    file_path,
    parameter="2t",
    level_type="heightAboveGround",
    level=2,
)
t2m.shape
```

:::{note}
`shortName` 由 ecCodes 的表格定义，与 ecCodes 版本有关。ecCodes
无法识别的要素（`shortName` 显示为 `unknown`）请改用下文的字典形式。
:::

### WGRIB2 要素名

reki 内置 WGRIB2 要素表格，下面的写法与 `"2t"` 完全等价：

```{code-cell} ipython3
t2m_wgrib2 = load_field_from_file(
    file_path,
    parameter="TMP",
    level_type="heightAboveGround",
    level=2,
)
bool((t2m_wgrib2 == t2m).all())
```

### CEMC 要素清单

reki 内置 CEMC 要素注册表，支持 CEMC 自定义变量名。注册表通过
`reki.format.grib.config.get_param_registry()` 查询：

```{code-cell} ipython3
import pandas as pd

from reki.format.grib.config import get_param_registry

registry = get_param_registry()
rows = []
for (discipline, category, number), entry in registry.items():
    rows.append({
        "name": entry["name"],
        "discipline": discipline,
        "category": category,
        "number": number,
        "wgrib2_name": entry.get("wgrib2_name"),
    })
param_table = pd.DataFrame(rows)
param_table.head(n=10)
```

CEMC 要素名可以附带层次信息。例如 `"t2m"` 在注册表中绑定了
`heightAboveGround`/2 米的层次条件，检索时无需再指定
`level_type`/`level`：

```{code-cell} ipython3
t2m_cemc = load_field_from_file(file_path, parameter="t2m")
bool((t2m_cemc == t2m).all())
```

:::{note}
注册表中的 CMA 模式特有要素名（如辐射亮温 `"bti"`、0–3 km 垂直风切变
`"shr(0-3000)"`）需要 CMA 模式 GRIB2 数据（CMA-HPC / CMADaaS 环境），
以下示例不参与执行：

```python
field = load_field_from_file(gfs_grib2_file_path, parameter="bti")
field = load_field_from_file(gfs_grib2_file_path, parameter="shr(0-3000)")
```
:::

### 字典形式（GRIB 键）

`parameter` 直接给 GRIB 键字典，适合名称表格覆盖不到的要素。
下面的写法与 `parameter="t"` 完全等价：

```{code-cell} ipython3
t500_dict = load_field_from_file(
    file_path,
    parameter={
        "discipline": 0,
        "parameterCategory": 0,
        "parameterNumber": 0,
    },
    level_type="pl",
    level=500,
)
t500_str = load_field_from_file(file_path, parameter="t", level_type="pl", level=500)
bool((t500_dict == t500_str).all())
```

## 层次（level_type / level）

层次键的背景（产品模板 4.0/4.8、双固定面、层次值计算公式）见新 API
文档 {doc}`/guide/grib_level`，本页只给出旧 API 的写法示例。

### typeOfLevel 字符串

`level_type` 给 ecCodes `typeOfLevel` 字符串，`level` 给对应层次值：

```{code-cell} ipython3
msl = load_field_from_file(file_path, parameter="msl", level_type="meanSea", level=0)
float(msl.mean())
```

### 内置层次别名

reki 内置三种层次别名：

| 别名 | 描述 | 等价的 GRIB 键条件 |
| --- | --- | --- |
| `pl` | 等压面层，单位 hPa | `typeOfFirstFixedSurface:int=100` |
| `sfc` | 地面层 | `typeOfLevel=surface` |
| `ml` | 模式面层 | `typeOfFirstFixedSurface:int=131` |

`pl` 支持浮点层次值（如 `level=1.5` 表示 1.5 hPa）；`sfc` 仅匹配
`typeOfLevel="surface"` 的要素：

```{code-cell} ipython3
tp = load_field_from_file(file_path, parameter="tp", level_type="sfc", level=0)
tp.shape
```

:::{note}
`ml`（模式面层）是 CMA 模式 modelvar 产品特有的层次类型，其 GRIB2
文件中所有要素使用同一层次类型，可以省略 `level_type`。以下示例需要
CMA-HPC 环境，不参与执行：

```python
field = load_field_from_file(
    gfs_modelvar_file_path,
    parameter="t",
    level_type="ml",
    level=20,
)
```
:::

### 字典形式的 level_type（GRIB 键）

`level_type` 接受字典，直接使用 GRIB 键作为筛选条件。
下面的写法与 `"heightAboveGround"` 等价（103 是码表 4.5 中
`heightAboveGround` 的编码值）：

```{code-cell} ipython3
t2m_dict = load_field_from_file(
    file_path,
    parameter="2t",
    level_type={"typeOfFirstFixedSurface:int": 103},
    level=2,
)
bool((t2m_dict == t2m).all())
```

:::{note}
键名中的 `:int` 后缀显式指定按键的整数形式比较。不标注类型时按键的
字符串形式比较，而 ecCodes 对常见编码值的字符串形式是别名而非数字
字符串，因此使用数值编码时请始终带上 `:int`。
:::

### 双层次要素：first_level / second_level

使用两个固定面定义层次的要素场（如土壤层，常见于产品模板 4.8），
可在 `level` 的字典形式中使用 reki 内置键 `first_level` /
`second_level`：

```python
# CMA-GFS 0.1–0.4 m 土壤温度层（typeOfLevel=depthBelowLandLayer）
field = load_field_from_file(
    gfs_grib2_file_path,
    parameter="t",
    level_type="depthBelowLandLayer",
    level={"first_level": 0.1, "second_level": 0.4},
)
```

:::{note}
上述双层次示例需要 CMA 模式 GRIB2 数据（CMA-HPC / CMADaaS 环境），
不参与执行。
:::

对单层次要素，`level` 的字典形式同样可用（此时只有 `first_level`
有意义）：

```{code-cell} ipython3
t2m_first = load_field_from_file(
    file_path,
    parameter="2t",
    level_type="heightAboveGround",
    level={"first_level": 2},
)
bool((t2m_first == t2m).all())
```

### 多层次检索

`reki.format.grib.load_fields_from_file()` 基于 cfgrib，
`level` 传入列表可一次加载多个层次，返回带层次维的
`xarray.Dataset`：

```{code-cell} ipython3
from reki.format.grib import load_fields_from_file

t_multi = load_fields_from_file(
    file_path,
    parameter="t",
    level_type="pl",
    level=[850, 500],
)
t_multi
```

## 任意 GRIB 键作为筛选条件

`load_field_from_file()` 支持将任意 GRIB 键作为关键字参数，
与其他条件组合使用。例如用 `stepType` 区分瞬时场与累计场：

```{code-cell} ipython3
tp_accum = load_field_from_file(
    file_path,
    parameter="tp",
    level_type="sfc",
    level=0,
    stepType="accum",
)
tp_accum.attrs["GRIB_stepType"], tp_accum.attrs["GRIB_stepRange"]
```

:::{note}
同名要素的不同统计量（如 CMA-MESO 输出间隔内的 10 米最大风
`stepType="max"`）也可以用这种方式区分。以下示例需要 CMA 模式
数据，不参与执行：

```python
field = load_field_from_file(
    meso_grib2_file_path,
    parameter="UGRD",
    level_type="heightAboveGround",
    level=10,
    stepType="max",
)
```
:::

## ecCodes 消息级 API

需要直接访问 GRIB 消息时，使用
`reki.format.grib.eccodes.load_message_from_file()`：它返回匹配条件的
**第一条**消息的 ecCodes 句柄（复制自原文件，文件已关闭），筛选参数与
`load_field_from_file()` 相同。句柄用完后必须调用
`eccodes.codes_release()` 释放。

```{code-cell} ipython3
import eccodes

from reki.format.grib.eccodes import load_message_from_file

message = load_message_from_file(
    file_path,
    parameter="gh",
    level_type="pl",
    level=500,
)
```

通过 ecCodes Python API 读取任意 GRIB 键和数据值，
数据值可以重组成二维数组：

```{code-cell} ipython3
values = eccodes.codes_get_double_array(message, "values")
ni = eccodes.codes_get_long(message, "Ni")
nj = eccodes.codes_get_long(message, "Nj")
values.reshape(nj, ni).shape
```

```{code-cell} ipython3
eccodes.codes_release(message)
```

:::{note}
**ecmwf_ifs 数据集包含修改后的 ECMWF IFS 开放数据**，© ECMWF，
按 CC-BY-4.0 许可使用。完整署名见 {doc}`/getting-started/test-data`。
:::
