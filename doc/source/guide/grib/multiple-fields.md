---
jupytext:
  text_representation: {extension: .md, format_name: myst}
kernelspec: {display_name: Python 3, language: python, name: python3}
---

# 多字段查询

`fetch_many()` 在一次 metadata 查找中执行多条独立查询，并保持输入顺序和重复项。它只适用
于 ecCodes GRIB reader；转换值仍是按字段延迟进行的。

```{code-cell} ipython3
from reki import from_source

reader = from_source("test", "ecmwf_ifs")
fields = reader.fetch_many(
    [
        {"parameter": "t", "level_type": "pl", "level": 850},
        {"parameter": "t", "level_type": "pl", "level": 500},
    ],
    cardinality="one",
)
assert [field.metadata.level for field in fields] == [850, 500]
```

批处理服务通常希望收集错误而非让一个缺失字段中断所有请求：

```{code-cell} ipython3
results = reader.fetch_many(
    [{"parameter": "missing"}, {"parameter": "t", "level": 850}],
    cardinality="one", errors="collect",
)
assert results[0].error is not None
assert results[1].metadata.level == 850
```

`errors="raise"`（默认）适合交互式使用；`errors="collect"` 返回带 `position` 和 `error`
的结果，以便调用者将失败对应回输入。
