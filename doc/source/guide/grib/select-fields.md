---
jupytext:
  text_representation: {extension: .md, format_name: myst}
kernelspec: {display_name: Python 3, language: python, name: python3}
---

# 选择字段

`sel()` 形成可继续细化的字段查询。先检查候选数量；只有业务上确实要求唯一字段时，
才调用 `one()`。`first()` 适合有明确排序约定的交互式探索。

```{code-cell} ipython3
from reki import from_source

reader = from_source("test", "ecmwf_ifs")
candidates = reader.sel(parameter="t", level_type="isobaricInhPa", level=[500, 850])
assert len(candidates.all()) == 2
selected = candidates.sel(level=500).all().one()
assert selected.metadata.level == 500
```

空查询不是错误，但把它当作唯一字段会失败。下面把“允许没有结果”的分支写清楚：

```{code-cell} ipython3
missing = reader.sel(parameter="not-a-grib-parameter").one_or_none()
assert missing is None
```

参数、层次和时间条件可一起使用；参见 {doc}`parameters`、{doc}`levels` 和
{doc}`time-and-step`。
