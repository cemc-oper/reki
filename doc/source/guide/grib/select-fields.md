---
jupytext:
  text_representation: {extension: .md, format_name: myst}
kernelspec: {display_name: Python 3, language: python, name: python3}
---

# 选择字段

`sel()` 使用唯一公共 Query；原生条件放在 `native.grib`。`one()` 要求唯一匹配，
`first()` 保留来源首匹配，`all()` 返回原序记录集合。

```{code-cell} ipython3
from reki import from_source
from reki.sources import get_source

# Test-data acquisition is separate from public query construction.
file_path = get_source("test", "ecmwf_ifs").mutate().path
source = from_source({"kind": "file", "path": str(file_path)})

selected = source.sel(native={"grib": {"shortName": "t"}}, level_type="pressure", level=850)
field = selected.one()
assert field.identity.to_dict()["level"] == 850
assert source.sel(native={"grib": {"parameterNumber": 250}}).first() is None
source.close()
```

`one_or_none()` 已退出。可选唯一场捕获 `QueryError(code="no_match")`；
`multiple_matches` 仍须传播，不能改成任取首场。`all()` 的空结果正常并携带 report，
需要独立预期域的完整性检查见 {doc}`/guide/public-query`。
