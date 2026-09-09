---
jupytext:
  text_representation:
    extension: .md
    format_name: myst
    format_version: 0.13
kernelspec:
  display_name: Python 3
  language: python
  name: python3
---

# 插值到目标网格

`interpolate_grid(data, target)` 将一个二维经纬度 `DataArray` 插值到 `target` 的坐标。
这与 `sample_nearest()` 不同：插值可生成新值，而抽稀只保留原网格点。使用固定 GRIB
数据构造一个较粗的目标网格：

```{code-cell} ipython3
from reki import from_source
from reki.operator import extract_region, interpolate_grid

field = from_source("test", "ecmwf_ifs").sel(
    parameter="2t", level_type="heightAboveGround", level=2,
).first()
assert field is not None
data = field.to_xarray()
target = extract_region(data, 105, 125, 25, 45).isel(
    latitude=slice(None, None, 8), longitude=slice(None, None, 8),
)
```

```{code-cell} ipython3
regridded = interpolate_grid(data, target, scheme="linear", engine="xarray")
assert regridded.dims == ("latitude", "longitude")
assert regridded.shape == target.shape == (11, 11)
assert regridded.latitude.identical(target.latitude)
assert regridded.longitude.identical(target.longitude)
regridded.shape
```

`engine="xarray"` 支持 xarray 的 `linear` 与 `nearest` 方案；`engine="scipy"` 还可用
SciPy 的方案和参数。两种 engine 不应被视为逐值相同的实现：明确选择 engine/方案，并
对边界外目标和缺测值检查输出。输入或 target 缺少一维 `latitude`/`longitude` 坐标会
立刻报错；曲线网格当前不受支持。
