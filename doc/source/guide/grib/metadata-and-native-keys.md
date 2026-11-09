---
jupytext:
  text_representation: {extension: .md, format_name: myst}
kernelspec: {display_name: Python 3, language: python, name: python3}
---

# Metadata 与原生键

Field.identity 描述输出身份；Field.metadata 保存 native_fields、来源与原始单位等证据。
这些记录只来自头扫描。原生查询不猜规范参数名，也不按 shortName 自动换算单位。

```{code-cell} ipython3
from reki import from_source
from reki.sources import get_source

# Test-data acquisition is separate from public query construction.
file_path = get_source("test", "ecmwf_ifs").mutate().path
source = from_source({"kind": "file", "path": str(file_path)})

field = source.sel(native={"grib": {"shortName": "t"}}, level_type="pressure", level=850).one()
assert field.metadata["native_fields"]["shortName"] == "t"
assert field.identity.to_dict()["level_type"] == "pressure"
source.close()
```

原生键在 `native.grib` 中显式给出，例如参数三元组、表版本、固定表面、PDT 和原始时钟。
只接受公共后端已支持的标量键。任意 ecCodes 条件仍可用于受保护的读取函数，其额外
过滤条件与公共 Query 分开，并在低频结果的 adapter provenance 保留。
