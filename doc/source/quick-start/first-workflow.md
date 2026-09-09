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

用 10～15 分钟完成一个可重复的闭环：准备固定 GRIB2 数据、建立 source、在不读取
values 的情况下探索、精确选择字段、转换为 `xarray.DataArray`，检查维度和坐标，最后
裁剪区域。先完成 {doc}`test-data` 的下载；以下单元只使用该冻结资产，不需要 CMA
内网、账号或当天的预报文件。

```{code-cell} ipython3
from reki import from_source
from reki.operator import extract_region
```

## 建立 source 并探索 header

使用规范入口 `from_source()` 创建 `test` source。`summary()`、`ls()`、`unique()` 和
`metadata()` 用于探索 header；`to_xarray()` 或 `values` 才会解码网格值。先列出可选择的
参数和层次：

```{code-cell} ipython3
source = from_source("test", "ecmwf_ifs")
parameters = source.unique("parameter")
levels = source.unique("level_type")
assert "2t" in parameters
assert "heightAboveGround" in levels
parameters, levels
```

## 精确选择并加载字段

`sel()` 只描述筛选条件；`first()` 明确要求一个匹配字段，`to_xarray()` 才解码为实际数据
数组。下面选择 2 米温度：

```{code-cell} ipython3
field = source.sel(
    parameter="2t",
    level_type="heightAboveGround",
    level=2,
).first()
assert field is not None
t2m = field.to_xarray()
assert t2m.name == "2t"
assert t2m.dims == ("latitude", "longitude")
assert t2m.shape == (241, 361)
t2m.name, t2m.dims, t2m.shape
```

检查范围和坐标名称，能避免把层次、预报时效或经纬度方向理解错：

```{code-cell} ipython3
checks = {
    "shape": t2m.shape,
    "latitude_range": (float(t2m.latitude.min()), float(t2m.latitude.max())),
    "longitude_range": (float(t2m.longitude.min()), float(t2m.longitude.max())),
}
assert checks["latitude_range"] == (0.0, 60.0)
assert checks["longitude_range"] == (60.0, 150.0)
checks
```

## 处理结果

将东亚的一部分区域裁剪出来。该操作保留已有格点，不进行插值：

```{code-cell} ipython3
east_asia = extract_region(
    t2m,
    start_longitude=105,
    end_longitude=125,
    start_latitude=25,
    end_latitude=45,
)
assert east_asia.dims == ("latitude", "longitude")
assert east_asia.shape == (81, 81)
east_asia.shape, (float(east_asia.latitude.min()), float(east_asia.latitude.max()))
```

没有匹配字段时，`first()` 返回 `None`。在自动化任务中应在解码前显式处理它：

```{code-cell} ipython3
missing = source.sel(parameter="not-a-grib-parameter").first()
if missing is None:
    print("没有匹配字段：请先用 unique()、ls() 或 GRIB 探索页查看可用参数和层次。")
```

此工作流没有需要调用者关闭的公开文件句柄；reki 在按需解码时管理文件访问。若你自行
通过 xarray 打开 Dataset 或持有其他外部资源，应按照该库的资源释放约定关闭它们。

下一步可进入：

- {doc}`/guide/finding/index`：选择本地、URL、目录或业务数据 source；
- {doc}`/guide/grib/index`：探索元数据、选择字段和理解 GRIB；
- {doc}`/guide/processing/index`：区域、站点和网格处理。
