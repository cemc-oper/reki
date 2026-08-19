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
- `**kwargs`：任意 GRIB 键作为筛选条件

```{code-cell} ipython3
first_message = ds.sel(count=1).to_xarray()
first_message.name
```

### 从本地文件加载

手头已有 GRIB 文件时，使用 `file` 数据源直接给出路径，之后的
`sel()` / `to_xarray()` 用法完全相同：

```python
ds = from_source("file", "/path/to/data.grib2")
field = ds.sel(parameter="t", level_type="isobaricInhPa", level=850).to_xarray()
```

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
