# Diagnostics 与错误

`collect_io_metrics()` 使用 context-local collector 记录 source 解析、文件打开、header
扫描、解码与 index 命中/未命中计数；它不改变读写策略或记录敏感配置。

```text
with collect_io_metrics() → reader events → IOMetricsSnapshot → application metrics
```

异常应保留具体语义：查询没有结果、多个结果、能力不支持、参数未映射和 catalog 错误均
不应压成普通 `ValueError`。日志和异常消息必须经 redact，不能输出 credential。API：
{doc}`../api/diagnostics`、{doc}`../api/core` 和 {doc}`../api/cmadaas`。
用户的 GRIB 诊断顺序与应保留的信息见 {doc}`/guide/grib/troubleshooting`；source/认证
故障的安全排查见 {doc}`/guide/finding/troubleshooting`。
