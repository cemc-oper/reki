# 远程与服务来源

CMADaaS 来源接受数据集 ID 和 CedarKit YAML 配置路径。读取时发出服务请求，
`explain()` 可先查看请求映射。安装、配置和读取说明见 {doc}`/guide/cmadaas-query`。

```python
from reki import from_source

source_options = {
    "kind": "cmadaas",
    "dataset": "cma_gfs_gmf_cmadaas",
    "config": "cedarkit.yaml",
}
with from_source(source_options) as source:
    selected = source.sel(parameter="cedarkit.t2m", time="2026-11-02T12:00:00Z", step="PT6H")
    explanation = selected.explain()
```

原 URL/named-plugin 工厂属于内部格式分派机制，不是公开 QuerySource 的 URL 支持承诺。
旧位置式 `from_source("url", ...)`、旧 CMADaaS 参数绑定及 `lazily=True` 来源构造已退出。
不要在日志中输出 token、password 或完整认证配置。来源访问、认证、超时和服务错误
由可靠底层异常分类为 `SourceError`，不能当作正常缺场处理。
