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

# 第一个 GRIB 工作流

使用测试数据说明 reki 库的基本使用方法，包括如下操作：

- 准备测试 GRIB2 数据
- 建立 source，在不读取 values 的情况下探索
- 精确选择要素场，转换为 `xarray.DataArray`
- 裁剪区域

```{code-cell} ipython3
from reki import from_source
from reki.operator import extract_region
```

请先完成 {doc}`test-data` 的下载，如果没有下载会在使用该数据时自动下载。

## 创建数据源并探索数据

使用规范入口 `from_source()` 创建 `test` source。
`summary()`、`ls()`、`unique()` 和 `metadata()` 用于探索 header；
`to_xarray()` 或 `values` 才会解码网格值。

使用 `ls()` 列出测试文件中的所有要素场：

```{code-cell} ipython3
source = from_source("test", "ecmwf_ifs")
source.ls()
```

可以使用 `unique()` 列出所有要素名称：

```{code-cell} ipython3
source.unique("parameter")
```

## 选择要素场

`sel()` 只描述筛选条件；`first()` 明确要求一个匹配字段，`to_xarray()` 才解码为实际数据数组。

下面选择 2 米温度：

```{code-cell} ipython3
field = source.sel(
    parameter="2t",
    level_type="heightAboveGround",
    level=2,
).first()
assert field is not None
t2m = field.to_xarray()
t2m
```

## 裁剪区域

将东亚的一部分区域裁剪出来。该操作保留已有格点，不进行插值：

```{code-cell} ipython3
east_asia = extract_region(
    t2m,
    start_longitude=105,
    end_longitude=125,
    start_latitude=25,
    end_latitude=45,
)
east_asia
```

## 空结果

没有匹配要素场时，`first()` 返回 `None`。在自动化任务中应在解码前显式处理它：

```{code-cell} ipython3
missing = source.sel(parameter="not-a-grib-parameter").first()
if missing is None:
    print("没有匹配字段：请先用 unique()、ls() 或 GRIB 探索页查看可用参数和层次。")
```

下一步可进入：

- {doc}`/guide/finding/index`：选择本地、URL、目录或业务数据 source；
- {doc}`/guide/grib/index`：探索元数据、选择字段和理解 GRIB；
- {doc}`/guide/processing/index`：区域、站点和网格处理。
