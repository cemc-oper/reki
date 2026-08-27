# 参数 ID 与 FieldQuery

`reki.resolve_parameter()` 将由 parameter-db 导出的只读快照中的稳定
`parameter_id`、规范名称、兼容 alias 或 wgrib2 名称解析为不可变的
`ResolvedParameter`。新 recipe 和新 Python 代码应优先使用 ID。

```python
import reki

resolved = reki.resolve_parameter("cedarkit.t2m")
assert resolved.record.unit == "K"
query = resolved.query
# FieldQuery(parameter={"discipline": 0, "parameterCategory": 0,
#                      "parameterNumber": 0},
#            level_type="heightAboveGround", level=2, ...)
```

解析顺序固定为精确 ID、规范名称、alias、外部（wgrib2）名称；不会进行
大小写、连字符或下划线的模糊匹配。未知名称会抛出
`ParameterNotFoundError`；同一层级的重复名称会在加载快照时以
`ParameterAmbiguityError` 失败。两个异常均提供稳定的 `code` 属性。

调用方只能补充泛化条目的条件，不能覆盖变体的固定语义：

```python
reki.resolve_parameter("cedarkit.t", level_type="isobaricInhPa", level=500)
reki.resolve_parameter("cedarkit.u10mmax-3").query.time_range  # Timedelta('0 days 03:00:00')
```

例如，给 `cedarkit.t2m` 传 `level=10` 会抛出
`ParameterConditionConflictError`。解析不打开文件、不导入 ecCodes/cfgrib，
也不做单位换算。`find_*()` 与 `convert_parameter()` 仍是兼容接口；后者对
未知字符串仍原样返回，不适用于新主路径。
