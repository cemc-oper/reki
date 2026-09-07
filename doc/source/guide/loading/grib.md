# GRIB

GRIB reader 支持参数、层次、时间、时效、时间范围、集合成员和原生键条件。优先使用
稳定 `parameter_id` 或规范参数名；`resolve_parameter()` 可解析外部命名空间，未知、
歧义和条件冲突分别以明确异常报告。

```python
field = from_source("file", "/data/example.grib2").sel(
    parameter="2t", level_type="heightAboveGround", level=2,
).first()
```

GRIB header 会映射为统一 metadata、坐标和属性。批量字段可先用 `ls()` / `unique()`；
需要大量重复探索时可选择持久 metadata index。index 会检查文件指纹并在过期、损坏或
不兼容时重建；只读 index 缺失时会失败，不能把它当作数据值缓存。

完整的参数名、层次别名、时效和原生键示例见 {doc}`/guide/grib_parameter`、
{doc}`/guide/grib_level` 与 {doc}`/guide/parameter_resolver`。ecCodes 消息级函数是
兼容边界，见 {doc}`legacy-api`。
