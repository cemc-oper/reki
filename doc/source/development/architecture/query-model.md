# 查询与 metadata 模型

Query / Request、身份、错误与报告来自 cedarkit-query，使用唯一 v1 schema。旧
SourceSpec / FieldQuery / FieldList / FieldMetadata 根导出及 one_or_none 已退出。

```text
source mapping + Query → selection.all / first / one → Fields / Field
                                                   → identity + metadata + report
```

one 使用 no_match / multiple_matches；准确数量与早停下界分别记录。DataArray 适配先
检查单变量，再核重复位置、网格与值；来源故障在实际遇到时报告，不通过提前解码破坏
惰性。内部 _Reader* / _SourceSpec 是格式分派记录，不是第二套公共模型。
协议详见 {doc}`/guide/public-query`；兼容面见 {doc}`/guide/migration`。
