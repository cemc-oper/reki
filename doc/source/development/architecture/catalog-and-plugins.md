# Catalog 与插件

Catalog 只解析配置并按 builtin、plugin、user 分层覆盖；解析阶段不导入 reader、不扫描路径
也不访问网络。最终记录产生可序列化 `SourceSpec`。

```text
builtin catalog + plugin catalog + user catalog → precedence merge → ResolvedDataset → SourceSpec
```

插件使用已声明的 catalog/source entry point，避免 import side effect。重复 ID 的覆盖来源
必须可追踪；无效 schema、循环别名和未知 source 应在解析时失败。API：
{doc}`../api/catalog`，扩展步骤见 {doc}`../extending/catalog-plugins`。
用户创建 source、使用 catalog 与 `file-pattern` 的路径见
{doc}`/guide/finding/catalogs-and-patterns`；本文不承诺部署目录或业务产品可用性。
