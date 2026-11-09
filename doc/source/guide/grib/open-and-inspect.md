---
jupytext:
  text_representation: {extension: .md, format_name: myst}
kernelspec: {display_name: Python 3, language: python, name: python3}
---

# 打开与探索

先扫描实际记录 metadata，再选择解码范围。公开 QuerySource 不使用旧 reader 的
`summary/head/ls/unique` 对象协议；原生头信息在 Field.metadata 中。

```{code-cell} ipython3
from reki import from_source
from reki.sources import get_source

# Test-data acquisition is separate from public query construction.
file_path = get_source("test", "ecmwf_ifs").mutate().path
source = from_source({"kind": "file", "path": str(file_path)})

fields = source.sel().all()
assert len(fields) > 0
headers = [dict(field.metadata["native_fields"]) for field in fields]
assert any(header["shortName"] == "2t" for header in headers)
source.close()
```

扫描和 explain 不解码网格值。选择及数量错误见 {doc}`select-fields`；
旧 `reki inspect/ls/query` 是独立的资料探索 CLI，不等于公共 Request CLI 的历史一致性验收。
