# 使用推荐 API 查找数据

`from_source(name, *args, **kwargs)` 是推荐入口；也可传入可序列化的 `SourceSpec`。
远程 `url` 与 `cmadaas` source 在首次访问数据对象时才执行 I/O，
`from_source_lazily()` 可把任何 source 的整个构建流程延后。

```python
from reki import SourceSpec, from_source

source = from_source("test", "ecmwf_ifs")
same_source = from_source(SourceSpec("test", ("ecmwf_ifs",)))
```

内置 source 包括 `test`、`file`、`file-pattern`、`local`、`url`、`memory` 与
`cmadaas`。`file` 接受一个已知路径；`file-pattern` 匹配多个本地文件；`memory`
包装数组或表格；`local` 根据 catalog/配置解析业务路径。`source_capability()` 可在
不触发远程 I/O 的情况下查看 source 声明的读取能力。

远程地址、凭据和本地目录都不应写进可共享示例。`SourceSpec` 的表示会脱敏敏感键；
捕获异常时同样不要记录 token、password 或完整服务配置。

数据集 catalog 的加载、覆盖顺序和 `SourceSpec` 解析见 {doc}`source-options`；选择
字段和实际加载见 {doc}`/guide/loading/new-api`。
