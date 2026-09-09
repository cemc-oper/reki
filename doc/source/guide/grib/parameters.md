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
{doc}`metadata-and-native-keys` 交叉验证。不要用展示名称或单位猜测参数：相同 shortName
在不同 discipline/category/number 或附加条件下可能表达不同记录。

## 参数 ID、外部名称与条件

`resolve_parameter()` 将稳定 parameter ID、规范名、alias 或已注册的外部名称解析为不可变
查询条件。`resolve_external_name()` 则按显式 namespace 查询一个规范参数对应的外部代码。
未知、歧义、命名空间不存在和调用条件与记录冲突，分别会报告明确的参数解析异常，而不会
回退到模糊匹配。

```python
from reki import resolve_parameter

resolved = resolve_parameter("HGT", level_type="isobaricInhPa", level=500)
query = resolved.query
```

字典形式的 `parameter` 是原生 GRIB 键条件，适合未注册的中心参数；它不是跨格式的用户
契约。完整签名、支持 namespace 和异常类型见 {doc}`/development/api/grib`，实现中的条件
合并规则见 {doc}`/development/architecture/parameter-resolution`。
