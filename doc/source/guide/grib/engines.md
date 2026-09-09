---
jupytext:
  text_representation: {extension: .md, format_name: myst}
kernelspec: {display_name: Python 3, language: python, name: python3}
---

# 读取引擎

默认 `engine="eccodes"` 提供字段列表、metadata、native-key 查询、`fetch_many()` 和
metadata index。`engine="cfgrib"` 用于与 cfgrib 生态兼容，但不提供这些探索接口。

```{code-cell} ipython3
from reki import from_source

eccodes_reader = from_source("test", "ecmwf_ifs", engine="eccodes")
assert eccodes_reader.capabilities.field_list
assert eccodes_reader.capabilities.fetch_many
```

两种引擎都可解码一个已经唯一的选择；把依赖 ecCodes 的操作留在选择之前：

```{code-cell} ipython3
cfgrib_reader = from_source("test", "ecmwf_ifs", engine="cfgrib")
assert not cfgrib_reader.capabilities.field_list
field = cfgrib_reader.sel(parameter="2t", level_type="heightAboveGround", level=2).to_xarray()
assert field.name == "2t"
```

如需确定的探索、批处理或索引行为，请使用默认 ecCodes 引擎。
