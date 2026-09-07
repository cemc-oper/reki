# 扩展 catalog 插件

catalog 插件提供可验证的静态记录，并让系统在不 I/O 的情况下合并为 `ResolvedDataset`。

```text
plugin catalog → schema validation → precedence merge → dataset ID / alias resolution
```

不要在插件导入时读取服务、环境变量或文件内容。为冲突覆盖、别名和无效 schema 编写测试；
将运行时参数放在 source 构造而不是 catalog 解析。API：{doc}`../api/catalog`。
