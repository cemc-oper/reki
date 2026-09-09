---
jupytext:
  text_representation: {extension: .md, format_name: myst}
kernelspec: {display_name: Python 3, language: python, name: python3}
---

# 惰性读取

字段列表和 metadata 探索不会解码网格值。只在选择已收窄后调用 `to_xarray()`，以控制 I/O
和内存边界。

```{code-cell} ipython3
from reki import from_source

reader = from_source("test", "ecmwf_ifs")
candidate = reader.sel(parameter="t", level_type="isobaricInhPa", level=850).all().one()
assert candidate.metadata.shape == (241, 361)
data = reader.sel(parameter="t", level_type="isobaricInhPa", level=850).to_xarray(lazy=True)
assert data.shape == (241, 361)
```

调用 `.values`、`numpy.asarray(data)` 或需要实际数值的聚合才会触发计算。若下游不支持
惰性数组，显式使用 `data.load()`，并确保选择条件已经把数据量限制在可接受范围内。
