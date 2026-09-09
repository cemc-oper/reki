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

# 裁剪区域、抽稀与提取站点

所有公开处理操作从 `xarray.DataArray` 开始。下面的 field 来自固定 GRIB2 数据，纬度为
升序或降序均可被 `extract_region()` 正确处理。

```{code-cell} ipython3
from reki import from_source
from reki.operator import extract_region, extract_point, sample_nearest

field = from_source("test", "ecmwf_ifs").sel(
    parameter="2t", level_type="heightAboveGround", level=2,
).first()
assert field is not None
data = field.to_xarray()
```

`extract_region()` 保留落在闭区间内的已有格点，不插值也不生成新值：

```{code-cell} ipython3
subset = extract_region(data, 105, 125, 25, 45)
assert subset.shape == (81, 81)
assert (float(subset.latitude.min()), float(subset.latitude.max())) == (25.0, 45.0)
assert (float(subset.longitude.min()), float(subset.longitude.max())) == (105.0, 125.0)
subset.shape
```

`sample_nearest()` 以输入第一个格点为锚点按步长抽取，是已有值的子集，不是站点插值：

```{code-cell} ipython3
coarse = sample_nearest(subset, longitude_step=2, latitude_step=2)
assert coarse.shape == (11, 11)
assert set(coarse.latitude.values).issubset(set(subset.latitude.values))
assert set(coarse.longitude.values).issubset(set(subset.longitude.values))
coarse.shape
```

`extract_point()` 为任意位置插值；`scheme="nearest"` 选择最近网格值，`linear` 由
xarray 插值。区域外点通常得到缺测值（或由所选 SciPy 方法报错），因此业务代码应在
使用前检查结果：

```{code-cell} ipython3
beijing = extract_point(data, latitude=39.9, longitude=116.4, scheme="nearest")
assert beijing.ndim == 0
assert float(beijing.latitude) == 39.9
assert float(beijing.longitude) == 116.4
float(beijing)
```
