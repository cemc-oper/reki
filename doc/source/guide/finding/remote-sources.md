# 远程与服务来源

当前公共服务来源使用声明式 CMADaaS dataset，连接及凭据来自调用方配置；实际请求在读取
时发生，explain 不访问服务。已接受范围、单位与响应错误见 {doc}`/guide/cmadaas-query`。

```python
from reki import from_source

with from_source({"kind": "cmadaas", "dataset": "cma_gfs_gmf_cmadaas"}) as source:
    selected = source.sel(parameter="cedarkit.t2m", time="2026-11-02T12:00:00Z", step="PT6H")
    explanation = selected.explain()
```

原 URL/named-plugin 工厂属于内部格式分派机制，不是公开 QuerySource 的 URL 支持承诺。
旧位置式 `from_source("url", ...)`、旧 CMADaaS 参数绑定及 `lazily=True` 来源构造已退出。
不要在日志中输出 token、password 或完整认证配置。来源访问、认证、超时和服务错误
由可靠底层异常分类为 `SourceError`，不能当作正常缺场处理。
