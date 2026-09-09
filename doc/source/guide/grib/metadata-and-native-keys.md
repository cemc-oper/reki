---
jupytext:
  text_representation: {extension: .md, format_name: myst}
kernelspec: {display_name: Python 3, language: python, name: python3}
---

# Metadata 与原生键

`metadata()` 和 `ls()` 返回 reki 的统一字段 metadata。它们只扫描 GRIB 头，不解码值；
先检查这些信息，再写选择条件。

```{code-cell} ipython3
from reki import from_source

reader = from_source("test", "ecmwf_ifs")
rows = reader.ls(["parameter", "level_type", "level", "step"])
assert set(rows["parameter"]) >= {"2t", "t", "gh"}
assert set(rows["level_type"]) >= {"heightAboveGround", "isobaricInhPa"}
```

`sel()` 的标准条件（如 `parameter`、`level_type`、`step` 和 `member`）应优先使用。
仅在数据源特有需求下传递原生 ecCodes 键；它们以显式关键字出现，并在 metadata 中交叉验证：

```{code-cell} ipython3
ensemble = from_source("test", "ecmwf_ifs", variant="ensemble")
perturbed = ensemble.sel(dataType="pf", step=24).all()
assert len(perturbed) == 20
assert {field.metadata.member for field in perturbed} == set(range(1, 21))
```

原生键不是跨格式契约，且带原生键的查询会执行头扫描而不是复用 v1 metadata index。
