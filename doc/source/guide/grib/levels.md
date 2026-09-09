---
jupytext:
  text_representation: {extension: .md, format_name: myst}
kernelspec: {display_name: Python 3, language: python, name: python3}
---

# 层次

层次由 `level_type` 和 `level` 共同定义。为了避免把相同数值的不同垂直坐标混在一起，
这两个条件应一起写出。

```{code-cell} ipython3
from reki import from_source

reader = from_source("test", "ecmwf_ifs")
t500 = reader.sel(parameter="t", level_type="isobaricInhPa", level=500).all().one()
assert t500.metadata.level_type == "isobaricInhPa"
assert t500.metadata.level == 500
```

层次别名可用于兼容已有代码，但新代码推荐使用标准 GRIB 类型名：

```{code-cell} ipython3
t850 = reader.sel(parameter="t", level_type="pl", level=850).all().one()
assert t850.metadata.level == 850
```

完整的单层、多层、土壤层与层结范围示例见 {doc}`/guide/grib_level`。
