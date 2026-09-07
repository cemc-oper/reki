# 选择与加载字段

`sel()` 接受参数、层次、时效、成员及格式支持的额外键，返回可继续筛选的查询对象。
`first()` 返回第一个匹配字段或 `None`；`all()` 返回 metadata 为主的 `FieldList`；
`to_xarray()` 读取值并返回统一数组。

```python
reader = from_source("test", "ecmwf_ifs")
query = reader.sel(parameter="2t", level_type="heightAboveGround", level=2)
field = query.first()
data = field.to_xarray() if field is not None else None
```

不要将 `first()` 当作“恰好一个”的保证：需要严格基数时使用 reader 提供的 `one()`
或显式处理 `DataNotFoundError` / `MultipleFieldsMatchedError`。查询只表达条件，不执行
值解码；大文件应先探索 metadata，再转换选中的字段。
