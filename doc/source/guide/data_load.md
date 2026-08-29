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

# 数据加载

本页介绍如何用 **reki** 加载各种格式的气象数据。GRIB 是主线格式，
示例使用内置 `test` 数据源的 **ecmwf_ifs** 冻结数据集
（说明见 {doc}`/getting-started/test-data`）；
GrADS、NetCDF 与表格小节展示 API 用法，需要自备数据文件。

## GRIB

reki 使用 ecCodes 解码 GRIB 数据。`from_source()` 返回的查询对象通过
`sel()` 按 GRIB 键筛选、`to_xarray()` 解码为 `xarray.DataArray`。

```{code-cell} ipython3
from reki import from_source

ds = from_source("test", "ecmwf_ifs")
```

### 加载单个要素场

`sel()` 的常用筛选条件：

- `parameter`：要素名（ecCodes shortName），如 `"2t"`、`"msl"`、`"10u"`
- `level_type`：层次类型（typeOfLevel），如 `"heightAboveGround"`、
  `"isobaricInhPa"`、`"meanSea"`、`"surface"`
- `level`：层次值

```{code-cell} ipython3
t2m = ds.sel(parameter="2t", level_type="heightAboveGround", level=2).to_xarray()
t2m
```

海平面气压（`meanSea` 层）：

```{code-cell} ipython3
msl = ds.sel(parameter="msl", level_type="meanSea", level=0).to_xarray()
float(msl.mean())
```

累计要素（如总降水 `tp`）带有 `stepType="accum"` 属性与
`GRIB_stepRange` 时间范围：

```{code-cell} ipython3
tp = ds.sel(parameter="tp", level_type="surface", level=0).to_xarray()
tp.attrs["GRIB_stepType"], tp.attrs["GRIB_stepRange"]
```

### 其他筛选方式

`sel()` 还支持：

- `count`：按消息在文件中的序号（从 1 开始）检索，设置后忽略其他条件
- `**kwargs`：任意 GRIB 键作为筛选条件（见下一小节）

```{code-cell} ipython3
first_message = ds.sel(count=1).to_xarray()
first_message.name
```

### 任意 GRIB 键作为筛选条件

除 `parameter` / `level_type` / `level` 之外，`sel()` 接受任意
GRIB 键作为关键字参数，可与其他条件组合使用。例如用 `stepType`
区分瞬时场（`instant`）与累计场（`accum`）：

```{code-cell} ipython3
tp = ds.sel(
    parameter="tp",
    level_type="surface",
    level=0,
    stepType="accum",
).to_xarray()
tp.attrs["GRIB_stepType"], tp.attrs["GRIB_stepRange"]
```

:::{note}
键的比较类型由值的 Python 类型自动推断（`str` → `:str`，
`int` → `:int`，`float` → `:float`）。对层次类型编码等
"字符串形式是别名"的 GRIB 键做数值比较时，需要在键名后显式加
`:int` 后缀（如 `typeOfFirstFixedSurface:int=103`），
详见 {doc}`/guide/grib_level` 中的说明。
:::

### ecCodes 消息级 API

需要直接访问 GRIB 消息元信息时（例如查看单位、网格定义等未进入
`xarray` 属性的 GRIB 键），可以使用
`reki.readers.grib.eccodes.load_message_from_file()`：
它返回匹配条件的**第一条**消息的 ecCodes 句柄（复制自原文件，
文件已关闭），之后可用 `eccodes.codes_get()` 读取任意 GRIB 键。
句柄用完后必须调用 `eccodes.codes_release()` 释放。

先取得数据文件路径（`test` 数据源定型为本地文件后，
其 `path` 属性即缓存文件路径）：

```{code-cell} ipython3
import eccodes

from reki.readers.grib.eccodes import load_message_from_file

file_path = ds.mutate().path
gid = load_message_from_file(
    file_path,
    parameter="gh",
    level_type="pl",
    level=500,
)
```

`load_message_from_file()` 的筛选参数与 `sel()` 相同
（`parameter` / `level_type` / `level` / `count` / 任意 GRIB 键）：

```{code-cell} ipython3
print(
    eccodes.codes_get(gid, "shortName"),
    eccodes.codes_get(gid, "level"),
    eccodes.codes_get(gid, "typeOfLevel"),
    eccodes.codes_get(gid, "units"),
)
print("grid:", eccodes.codes_get(gid, "Ni"), "x", eccodes.codes_get(gid, "Nj"))
eccodes.codes_release(gid)
```

### 从本地文件加载

手头已有 GRIB 文件时，使用 `file` 数据源直接给出路径，之后的
`sel()` / `to_xarray()` 用法完全相同：

```python
ds = from_source("file", "/path/to/data.grib2")
field = ds.sel(parameter="t", level_type="isobaricInhPa", level=850).to_xarray()
```

### 先探索元数据，再解码数据

使用 ecCodes GRIB reader 时，`all()` 返回惰性字段集合；`summary()`、
`metadata()`、`unique()`、`head()` 和 `ls()` 只读取消息头，不会加载网格
values。可先用这些接口确认可用字段，再对选中的字段调用 `to_xarray()`。

```python
fields = ds.all()
fields.summary()
fields.ls(["parameter", "level_type", "level"])
fields.where(parameter="t").unique("level")

# experimental：多个条件共享一次元数据读取，结果保持输入顺序
selected = ds.fetch_many(
    [{"parameter": "t", "level_type": "pl", "level": 850},
     {"parameter": "t", "level_type": "pl", "level": 500}],
    cardinality="one",
)
data = selected[0].to_xarray()
```

`where()` 仅接受 `FieldQuery` 或显式的键值条件，不能执行 Python/SQL
表达式。`reader.capabilities` 可用于在调用前检查格式是否支持元数据探索；
目前完整探索和 `fetch_many()` 仅适用于 `engine="eccodes"` 的 GRIB。

:::{note}
**ecmwf_ifs 数据集包含修改后的 ECMWF IFS 开放数据**，© ECMWF，
按 CC-BY-4.0 许可使用。完整署名见 {doc}`/getting-started/test-data`。
:::

## GrADS

:::{note}
本小节为 API 用法说明，示例代码需要 GrADS 数据文件（ctl + 二进制数据），
不参与文档构建执行。
:::

reki 内置简单的 GrADS 格点二进制格式解析器，传入数据描述文件（ctl）路径：

```python
from reki import from_source

ds = from_source("file", "/path/to/post.ctl_2021101500_036")
t850 = ds.sel(parameter="t", level_type="pl", level=850).to_xarray()
```

支持单一描述文件对应多个数据文件（如 GRAPES TYM 的 POSTVAR 数据）。

## NetCDF

:::{note}
本小节为 API 用法说明，示例代码需要 NetCDF 数据文件，不参与文档构建执行。
:::

NetCDF 读取基于 xarray：

```python
from reki import from_source

ds = from_source("file", "/path/to/data.nc")
da = ds.to_xarray()
```

## 表格数据

:::{note}
本小节为 API 用法说明，示例代码需要表格数据文件，不参与文档构建执行。
:::

表格数据（如观测资料）解析为 `pandas.DataFrame`：

```python
from reki import from_source

ds = from_source("file", "/path/to/obs.dat")
df = ds.to_pandas()
```
