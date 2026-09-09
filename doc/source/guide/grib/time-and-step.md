---
jupytext:
  text_representation: {extension: .md, format_name: myst}
kernelspec: {display_name: Python 3, language: python, name: python3}
---

# 时间、时效与时间范围

`time` 是起报时间，`step` 是预报时效；`valid_time` 是二者合成的有效时间。不要从
文件名或字段顺序推断它们，而应直接读取 metadata 或 xarray 坐标。

```{code-cell} ipython3
from reki import from_source

reader = from_source("test", "ecmwf_ifs", variant="time")
fields = reader.sel(
    parameter="2t", level_type="heightAboveGround", level=2, step=[0, 6, 12, 24],
).all()
assert len(fields) == 4
assert {field.metadata.step.total_seconds() / 3600 for field in fields} == {0, 6, 12, 24}
```

聚合或累计变量还必须检查 GRIB 的时间范围键，不能把单点时效误当作累计区间：

```{code-cell} ipython3
precipitation = reader.sel(parameter="tp", level_type="surface", level=0, step=24).all().one()
metadata = precipitation.metadata
assert metadata.step.total_seconds() / 3600 == 24
assert metadata.parameter == "tp"
assert metadata.step_type == "accum"
assert metadata.time_range.total_seconds() / 3600 == 24
```

需要带标签数组时，请继续阅读 {doc}`xarray-output`。
