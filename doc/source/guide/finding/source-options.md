# Source 选项、catalog 与环境

`file`、`file-pattern` 和 `memory` 适合由调用者直接提供数据位置或对象。`local` 把
产品标识、时间和成员等参数解析为路径；它需要与部署匹配的配置。CMA-HPC、CMADaaS
挂载盘和 CMADaaS 服务均是环境专属能力，应在运行环境中设置凭据和路径，不应作为
可执行文档示例的前提。

```python
from reki import from_source

reader = from_source("file", "/data/example.grib2")
lazy_remote = from_source("url", "https://example.invalid/data.grib2")
```

路径模板、成员参数和本地调试沿用 `local` source 的配置层；遇到路径不存在时先确认
起报时间、时效、成员和 storage 层级，再检查配置渲染结果。服务端失败应在首次
`ls()`、`metadata()` 或转换时处理，而不是假定创建 source 已完成访问。

Catalog 只解析配置，不扫描文件或访问网络：

```python
from reki import load_catalog

resolved = load_catalog().resolve("my_dataset")
reader = resolved.source
```

catalog 的记录、覆盖规则和插件扩展属于开发主题；用户只需将已解析的 `SourceSpec`
传回 `from_source()`。旧 YAML/Jinja2 data_finder 格式见 {doc}`legacy-api`。
