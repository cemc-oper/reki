# 远程与服务 source

`url` 从一个明确的 URL 读取，`cmadaas` 通过 CMADaaS MUSIC 服务请求数据。二者的网络、
凭据、可用产品和限流均取决于部署，因而不能作为可重复文档单元的前提。

```python
from reki import from_source

remote = from_source("url", "https://host.example/forecast.grib2")
service = from_source(
    "cmadaas", interface_id="getNafpEleGrid",
    params={"dataCode": "YOUR_PRODUCT", "time": "2026090712"},
)
```

建立 source 不等于请求已经成功：在 `ls()`、`metadata()`、`sel()` 或转换方法首次需要
数据时，捕获网络、认证和服务端异常。日志中不要输出 token、password、完整请求头或
`SourceSpec` 的未脱敏原始内容。

需要延后整个 source 构建流程时传 `lazily=True`，其可执行的内存示例见 {doc}`new-api`。
在接入服务前，先用 {doc}`/quick-start/first-workflow` 的冻结数据确认查询和处理逻辑。
