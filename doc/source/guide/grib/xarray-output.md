---
jupytext:
  text_representation: {extension: .md, format_name: myst}
kernelspec: {display_name: Python 3, language: python, name: python3}
---

# xarray 输出

`to_xarray()` 返回带坐标的 `xarray.DataArray`（必要时为 `Dataset`）。数据维度来自 GRIB
网格和选择结果，所以先断言可观察坐标和维度，再进行计算。

```{code-cell} ipython3
from reki import from_source

data = from_source("test", "ecmwf_ifs", variant="time").sel(
    parameter="2t", level_type="heightAboveGround", level=2, step=[0, 6, 12, 24],
).to_xarray()
assert data.step.values.astype("timedelta64[h]").astype(int).tolist() == [0, 6, 12, 24]
assert "valid_time" in data.coords
```

沿命名维度计算，不要依赖数组轴号：

```{code-cell} ipython3
zonal_mean = data.mean("latitude")
assert zonal_mean["2t"].dims == ("heightAboveGround", "longitude")
```

集合数组的成员坐标为 `number`；控制预报为 0。详见 {doc}`ensemble`，以及旧链接
{doc}`/guide/loading/xarray-output` 的兼容说明。
