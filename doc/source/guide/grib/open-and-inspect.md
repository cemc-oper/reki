---
jupytext:
  text_representation: {extension: .md, format_name: myst}
kernelspec: {display_name: Python 3, language: python, name: python3}
---

# 打开与探索

先读取 header，再决定要解码的字段。`summary()`、`head()`、`ls()` 和 `unique()` 都不读取 values。

```{code-cell} ipython3
from reki import from_source

reader = from_source("test", "ecmwf_ifs")
summary = reader.summary()
parameters = reader.unique("parameter")
assert summary["field_count"] == 11
assert "2t" in parameters and "t" in parameters
reader.head(2).ls(["parameter", "level_type", "level"])
```

接下来用 {doc}`select-fields` 把探索结果变成精确选择。
