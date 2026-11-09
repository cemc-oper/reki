# 架构概览

公开构造仅接受声明式 source mapping，并使用 cedarkit-query 的唯一 v1 Query / Request。

```text
source declaration + context → QuerySource → selection → Fields / Field
                                           → report / metadata → Dataset → operator
```

metadata 定位与值解码分离；实际范围、来源与证据由报告保存。受保护高频旧函数直接走
原生 ecCodes 内核以保留 first-match / lazy 行为；低频适配复用公共组织和冲突检查。
内部命名格式 / 插件分派仍用私有记录，不对外提供旧 SourceSpec / FieldQuery 协议窗口。
API 见 {doc}`../api/top-level`，格式边界见 {doc}`grib-reader-and-index`。
