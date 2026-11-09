---
orphan: true
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
接口。这些函数按本页限定范围保留；已退出的引擎、索引与旧模型须迁移。新代码请使用公共 API
（`from_source()` / `sel()` / `to_xarray()`），见
{doc}`/guide/grib/index`、{doc}`/guide/grib/parameters`、
{doc}`/guide/grib/levels`。新旧接口的对应关系见
{doc}`/guide/migration`。
:::

`reki.format.grib.load_field_from_file()` 从 GRIB 文件中加载**单个**
要素场，返回 `xarray.DataArray`（未找到时返回 `None`）。常用参数：

- `file_path`：GRIB 文件路径
- `parameter`：要素名（字符串或 GRIB 键字典）
- `level_type`：层次类型（字符串或 GRIB 键字典）
- `level`：层次值
- `engine`：解码引擎，仅 `"eccodes"`；显式 `"cfgrib"` 报 unsupported
- `**kwargs`：任意 GRIB 键作为附加筛选条件

本页示例使用内置 `test` 数据源的 **ecmwf_ifs** 冻结数据集
（说明见 {doc}`/quick-start/test-data`）。下面的代码单元仅用
新 API 取得缓存文件路径，本页其余代码均为旧 API 写法，
除标注外均可执行：

```{code-cell} ipython3
from reki.sources import get_source

file_path = get_source("test", "ecmwf_ifs").mutate().path
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

## 参数筛选

消息读取的 `parameter` 接受 ecCodes shortName 或原生键字典。使用报文序号时传 `count`。需要区分本地编码时可使用参数三元组、表版本和固定面类型等键。

## 层次（level_type / level）

层次键的背景（产品模板 4.0/4.8、双固定面、层次值计算公式）见新 API
文档 {doc}`/guide/grib/levels`，本页只给出旧 API 的写法示例。

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
t2m = load_field_from_file(file_path, parameter="2t", level_type="heightAboveGround", level=2)
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

`reki.format.grib.load_fields_from_file()` 使用 ecCodes 与公共 v1 组织／报告，
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
按 CC-BY-4.0 许可使用。完整署名见 {doc}`/quick-start/test-data`。
:::

## 当前保护边界

高频单文件保留原序与首匹配、部分层列表、原生坐标／单位／命名及 lazy，不强加报告。
低频多文件 DataArray / 单文件 Dataset 使用公共维度、去重、冲突和网格规则；
level=None / "all" 不加层值限制，多文件 field_name 只重命名单变量，显式 level_dim
或 lazy=True 报 unsupported。零匹配分别返回 None / 携带报告的空 Dataset。

低频报告为 cedarkit_query_report JSON；额外原生过滤条件记录在 adapter provenance，
不扩展公共 schema。cfgrib 命名路径已删除。with_index True / 字符串只在调用处发出
一次 FutureWarning，False 无提示，索引路径零访问。消息 / 字节返回原生顺序与所有权，
count 为一基物理序号且优先于条件。来源与查询错误使用公共 SourceError / QueryError。
