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

# 快速开始

本页通过一个完整的小例子演示 **reki** 的典型用法：从数据源获取要素场，
转为 `xarray.DataArray`，再做简单的区域裁剪。

示例使用 reki 内置 `test` 数据源提供的 **ecmwf_ifs** 冻结数据集
（ECMWF IFS 0.25° 东亚区域子集，起报时次 2026-08-18 00 UTC，+24h）。
首次运行会自动下载（约 800 KB），之后离线可用。
数据集的详细说明见 {doc}`test-data`。

```{code-cell} ipython3
from reki import from_source
```

## 获取数据

`from_source()` 是 reki 的统一数据入口。第一个参数是数据源名称，
这里使用内置的 `test` 数据源并指定 `ecmwf_ifs` 数据集：

```{code-cell} ipython3
ds = from_source("test", "ecmwf_ifs")
ds
```

## 检索要素场

数据源返回的是查询对象，使用 `sel()` 按 GRIB 键筛选要素场。
下面的代码检索 2 米温度（`2t`，`heightAboveGround` 层，2 米）：

```{code-cell} ipython3
field = ds.sel(parameter="2t", level_type="heightAboveGround", level=2)
field
```

`sel()` 只做筛选、不读取数据。调用 `to_xarray()` 将要素场解码为
`xarray.DataArray`：

```{code-cell} ipython3
t2m = field.to_xarray()
t2m
```

返回的 `DataArray` 包含维度坐标（`latitude`、`longitude`）、时间坐标
（`time`、`step`、`valid_time`）以及 GRIB 元数据属性：

```{code-cell} ipython3
t2m.attrs["long_name"], t2m.attrs["GRIB_validityDate"]
```

之后即可使用 xarray 生态的全部工具，例如计算区域平均：

```{code-cell} ipython3
float(t2m.mean())
```

## 裁剪区域

`reki.operator` 提供常用的格点操作。下面的代码用 `extract_region`
裁剪出 25–45°N、105–125°E 的区域：

```{code-cell} ipython3
from reki.operator import extract_region

region = extract_region(
    t2m,
    start_longitude=105,
    end_longitude=125,
    start_latitude=25,
    end_latitude=45,
)
region.shape
```

更多操作（插值、站点提取等）见 {doc}`/guide/data_process`。

## 下一步

- {doc}`/guide/data_find`：数据源与读取器体系，以及各数据源的用法
- {doc}`/guide/data_load`：GRIB、GrADS、NetCDF、表格等格式的加载方法
- {doc}`/guide/data_process`：区域裁剪、站点提取、网格插值等数据处理操作
