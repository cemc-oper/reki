---
jupytext:
  text_representation: {extension: .md, format_name: myst}
kernelspec: {display_name: Python 3, language: python, name: python3}
---

# 参数

优先使用 GRIB/ecCodes 的规范 `shortName`，例如 `2t`、`t` 和 `gh`。参数名称本身
不足以唯一定位字段，因此应始终同时限制层次。

```{code-cell} ipython3
from reki import from_source

reader = from_source("test", "ecmwf_ifs")
temperature = reader.sel(
    parameter="2t", level_type="heightAboveGround", level=2,
).all().one()
assert temperature.metadata.parameter == "2t"
assert temperature.metadata.level == 2
```

已注册的 WGRIB2 名称也可解析，适合迁移已有查询；结果仍应以规范 metadata 验证：

```{code-cell} ipython3
geopotential_height = reader.sel(
    parameter="HGT", level_type="isobaricInhPa", level=500,
).all().one()
assert geopotential_height.metadata.parameter == "gh"
```

自定义中心参数或有歧义的别名请使用稳定的数字 GRIB 键，并参阅
{doc}`/guide/grib_parameter` 的完整映射说明。
