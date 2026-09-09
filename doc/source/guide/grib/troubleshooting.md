---
jupytext:
  text_representation: {extension: .md, format_name: myst}
kernelspec: {display_name: Python 3, language: python, name: python3}
---

# 排错

先以 metadata 证实文件内容和查询基数，再解码值。大多数“读不到数据”问题来自参数、层次、
时效或成员条件不一致。

| 现象 | 检查与处理 |
| --- | --- |
| 没有匹配字段 | `ls --json` 或 `reader.ls()` 查看实际 `parameter`、`level_type`、`level`、`step` 和 `member`。|
| `one()` 报多个匹配 | 增加层次、时效、时间范围或成员条件；不要任意改用 `first()`。|
| IFS 控制预报未命中 | 使用公共 `member=0`；控制原生没有 `number` 键。|
| index 只读失败 | 先以 `auto` 建立 index，或改为 `off` 进行一次性头扫描。|
| cfgrib 没有 `ls()`/`fetch_many()` | 切换到默认 `engine="eccodes"`。|

最小诊断流程如下：

```{code-cell} ipython3
from reki import from_source

reader = from_source("test", "ecmwf_ifs")
available = reader.ls(["parameter", "level_type", "level", "step"])
assert not available.empty
field = reader.sel(parameter="t", level_type="isobaricInhPa", level=850).one()
assert field.to_xarray().name == "t"
```

如果问题仍存在，请记录 `reki inspect --json` 输出、查询条件、引擎、index 策略和完整异常；
不要在报告中附带不必要的原始数据值。
