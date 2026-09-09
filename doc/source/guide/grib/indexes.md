---
jupytext:
  text_representation: {extension: .md, format_name: myst}
kernelspec: {display_name: Python 3, language: python, name: python3}
---

# Metadata index

对同一 GRIB 文件反复做 metadata 查询时，可用持久 SQLite index 避免重复头扫描。index 是
可再建的 metadata 加速层，不保存已解码的网格值；源文件指纹改变时会自动失效。

```{code-cell} ipython3
from pathlib import Path
from tempfile import TemporaryDirectory

from reki import from_source

temporary_index = TemporaryDirectory()
cache = Path(temporary_index.name)
test_reader = from_source("test", "ecmwf_ifs")
reader = from_source("file", test_reader.path, index_policy="auto", index_dir=cache)
fields = reader.sel(parameter="t", level_type="isobaricInhPa").all()
assert {field.metadata.level for field in fields} == {500, 850}
assert list(cache.glob("*.sqlite"))
```

`readonly` 适用于不可写环境：若没有有效 index，它会失败而不是悄悄创建文件。`refresh`
强制重建；`off` 禁用 index，适合一次性的查询或诊断。

```{code-cell} ipython3
readonly = from_source("file", test_reader.path, index_policy="readonly", index_dir=cache)
assert readonly.sel(parameter="gh", level=500).all().one().metadata.parameter == "gh"
```

含原生 GRIB 键的查询会回退到头扫描，保证不会因 index 缺少非标准键而得到错误结果。
