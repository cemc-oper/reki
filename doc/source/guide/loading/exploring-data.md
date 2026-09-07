# 探索元数据

在读取数值前，使用 `ls()`、`metadata()` 和 `unique()` 查看可用字段。它们返回或操作
`FieldList` / `FieldMetadata`，可以切片、组合并继续 `sel()`，因此适合先确认参数、层次
和时效。

```python
fields = from_source("test", "ecmwf_ifs").ls()
fields.ls(["parameter", "level_type", "level"])
fields.unique("parameter")
```

不同 reader 的能力不同；不支持的 metadata 或转换会抛出 `UnsupportedOperationError`。
对 GRIB，metadata 探索通常只扫描 header，不解码格点值；索引策略和任意键查询见
{doc}`grib`。
