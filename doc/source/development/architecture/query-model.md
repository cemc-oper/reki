# 查询与 metadata 模型

`SourceSpec`、`FieldQuery` 和 metadata/list 对象是不可变的输入/描述模型；筛选返回新
对象，不会通过表达式执行任意代码。

```text
FieldQuery + FieldMetadata → FieldList.sel() → 新 FieldList → first/all → Field
```

标准键与 `extra` 原生键在构造时分离并规范化。常见失败是混用位置 `FieldQuery` 与关键字
过滤、或假定 `first()` 表示唯一匹配；应使用明确的基数错误处理。扩展 reader 时必须让
metadata 支持同样的选择语义。API：{doc}`../api/core`。
用户应从 {doc}`/guide/grib/select-fields` 学习查询、基数与零匹配处理，从
{doc}`/guide/grib/metadata-and-native-keys` 学习 header metadata；不要将本页的内部模型
描述当作另一份教程。
