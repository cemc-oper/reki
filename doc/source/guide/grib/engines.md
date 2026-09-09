---
jupytext:
  text_representation: {extension: .md, format_name: myst}
kernelspec: {display_name: Python 3, language: python, name: python3}
---

# 读取引擎

默认 `engine="eccodes"` 提供字段列表、metadata、native-key 查询、`fetch_many()` 和
metadata index。当前 `engine="cfgrib"` 也经由同一 GRIB reader dispatch 提供这些公开
能力；它是兼容的 engine 选择，不是功能更少的 reader。

```{code-cell} ipython3
from reki import from_source

eccodes_reader = from_source("test", "ecmwf_ifs", engine="eccodes")
assert eccodes_reader.capabilities.field_list
assert eccodes_reader.capabilities.fetch_many
```

两种引擎都可解码一个已经唯一的选择，并暴露相同的本次查询能力：

```{code-cell} ipython3
cfgrib_reader = from_source("test", "ecmwf_ifs", engine="cfgrib")
assert cfgrib_reader.capabilities.field_list
assert cfgrib_reader.capabilities.fetch_many
field = cfgrib_reader.sel(parameter="2t", level_type="heightAboveGround", level=2).to_xarray()
assert field.name == "2t"
```

需要与现有 cfgrib 配置互操作时可显式选择该 engine；默认 ecCodes 仍是本文档示例的推荐值。
