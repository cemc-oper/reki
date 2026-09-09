---
jupytext:
  text_representation: {extension: .md, format_name: myst}
kernelspec: {display_name: Python 3, language: python, name: python3}
---

# 层次

层次由 `level_type` 和 `level` 共同定义。为了避免把相同数值的不同垂直坐标混在一起，
这两个条件应一起写出。选择时可用 GRIB 的 `isobaricInhPa`，而统一 metadata 将等压面
表示为兼容的 `pl` 名称。

```{code-cell} ipython3
from reki import from_source

reader = from_source("test", "ecmwf_ifs")
t500 = reader.sel(parameter="t", level_type="isobaricInhPa", level=500).all().one()
assert t500.metadata.level_type == "pl"
assert t500.metadata.level == 500
```

层次别名可用于兼容已有代码，但新代码推荐使用标准 GRIB 类型名：

```{code-cell} ipython3
t850 = reader.sel(parameter="t", level_type="pl", level=850).all().one()
assert t850.metadata.level == 850
```

## 多层与层状字段

同一参数的多个等压面应以列表选择，并在结果中检查层次坐标而不是依赖消息顺序：

```{code-cell} ipython3
layers = reader.sel(parameter="t", level_type="isobaricInhPa", level=[500, 850]).to_xarray()
assert sorted(layers["t"].isobaricInhPa.values.tolist()) == [500, 850]
```

`soilLayer` 等层状字段还包含原生的上下界；`level` 只是层标识，不能替代边界。固定
`layers` variant 提供 soilLayer 1/2 与 0–1 m、1–2 m 边界，具体 metadata 查询见
{doc}`metadata-and-native-keys`。需要按第一/第二固定层表面选择的产品，应传原生 GRIB
键并在 header 中验证；可用 key 的 API 见 {doc}`/development/api/grib`。
