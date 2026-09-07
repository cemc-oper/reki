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

# 第一个工作流

本例使用 {doc}`test-data` 中的冻结数据，依次建立数据源、选择一个字段、转换为
`xarray.DataArray`，然后裁剪区域。`from_source()` 返回的是数据对象（这里是 GRIB
读取器）；`sel()` 返回查询结果；`to_xarray()` 返回实际数据数组。

```{code-cell} ipython3
from reki import from_source
from reki.operator import extract_region
```

## 查找数据

使用规范入口 `from_source()` 创建 `test` source。数据尚未下载时，首次实际读取会
使用已准备的冻结资产：

```{code-cell} ipython3
source = from_source("test", "ecmwf_ifs")
source
```

## 选择并加载字段

`sel()` 只描述筛选条件；下面选择 2 米温度。`first()` 明确要求一个匹配字段，
`to_xarray()` 才解码为 `xarray.DataArray`：

```{code-cell} ipython3
field = source.sel(
    parameter="2t",
    level_type="heightAboveGround",
    level=2,
).first()
t2m = field.to_xarray()
t2m
```

返回值是带 `latitude`、`longitude`、时间和 GRIB 属性的 `DataArray`：

```{code-cell} ipython3
t2m.dims, t2m.name
```

## 处理结果

将东亚的一部分区域裁剪出来：

```{code-cell} ipython3
east_asia = extract_region(
    t2m,
    start_longitude=105,
    end_longitude=125,
    start_latitude=25,
    end_latitude=45,
)
east_asia.shape
```

此工作流没有需要调用者关闭的公开文件句柄；reki 在按需解码时管理文件访问。若你自行
通过 xarray 打开 Dataset 或持有其他外部资源，应按照该库的资源释放约定关闭它们。

下一步可进入：

- {doc}`/guide/data_find`：选择本地、URL、目录或业务数据 source；
- {doc}`/guide/data_load`：探索元数据、选择字段和理解不同格式；
- {doc}`/guide/data_process`：区域、站点和网格处理。
