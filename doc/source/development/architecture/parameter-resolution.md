# 参数解析

registry 将稳定 parameter ID、别名和外部命名空间映射为带条件的 `FieldQuery`；resolver
先确定记录，再合并调用者可补充的条件，拒绝覆盖固定语义。

```text
name / ID / namespace → registry index → record → condition merge → ResolvedParameter
                                      ↘ unknown / ambiguous / conflict
```

新增 registry 数据必须经 SQLite 导出流程，不能手改生成注册表。常见失败是外部名称未映射、
重复别名和与记录冲突的层次条件。API：{doc}`../api/grib`。
