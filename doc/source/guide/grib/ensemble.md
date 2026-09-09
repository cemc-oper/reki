---
jupytext:
  text_representation: {extension: .md, format_name: myst}
kernelspec: {display_name: Python 3, language: python, name: python3}
---

# 集合预报

冻结 ensemble 资产包含 IFS 确定性控制预报和 PF 1–20。在公共查询中，控制预报为
`member=0`；转为 xarray 后，它是 `number=0`。这使控制和扰动成员能在同一成员维上处理。

```{code-cell} ipython3
from reki import from_source

reader = from_source("test", "ecmwf_ifs", variant="ensemble")
step_24 = reader.sel(
    parameter="2t", level_type="heightAboveGround", level=2, step=24,
).all()
control = step_24.sel(member=0).one()
members = step_24.sel(member=list(range(21)))
assert control.metadata.member == 0
assert {field.metadata.member for field in members} == set(range(21))
```

集合统计前应固定参数、层次、时效及成员集合：

```{code-cell} ipython3
data = members.to_xarray()
assert data.number.values.tolist() == list(range(21))
ensemble_mean = data.mean("number")
assert "number" not in ensemble_mean.dims
```

原生控制消息没有 GRIB `number` 键；不要据此过滤控制消息，使用公共 `member=0` 即可。
