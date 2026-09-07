---
jupytext:
  text_representation:
    extension: .md
    format_name: myst
    format_version: 0.13
    jupytext_version: 1.16.0
kernelspec:
  display_name: Python 3
  language: python
  name: python3
---

# 探索元数据

在读取数值前，使用 `ls()`、`metadata()` 和 `unique()` 查看可用字段。它们返回或操作
`FieldList` / `FieldMetadata`，可以切片、组合并继续 `sel()`，因此适合先确认参数、层次
和时效。

```{code-cell} ipython3
from reki import from_source

reader = from_source("test", "ecmwf_ifs")
fields = reader.ls()
fields.ls(["parameter", "level_type", "level"])
```

```{code-cell} ipython3
sorted(fields.unique("parameter"))[:10]
```

得到候选参数后，再将其中一个条件带入 `sel()`。这一步仍只处理 metadata；只有
`to_xarray()`、`to_numpy()` 或 `to_pandas()` 才要求 reader 解码数值：

```{code-cell} ipython3
candidate = reader.sel(parameter="2t", level_type="heightAboveGround", level=2).first()
candidate is not None
```

不同 reader 的能力不同；不支持的 metadata 或转换会抛出 `UnsupportedOperationError`。
对 GRIB，metadata 探索通常只扫描 header，不解码格点值；索引策略和任意键查询见
{doc}`grib`。
