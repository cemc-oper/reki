# Source 选项、catalog 与环境

公开 file 声明显式给出单文件、文件列表或有序 glob；local 声明给出 dataset 和部署 root。
构造只绑定配置，不承诺任何业务资料或服务可用。

```python
from reki import from_source

with from_source({"kind": "file", "path": "/data/example.grib2"}) as source:
    selected = source.sel(native={"grib": {"shortName": "t"}}).all()

with from_source({"kind": "local", "dataset": "cma_gfs_gmf", "root": "/CMADAAS"}) as source:
    query = source.sel(time="2026-11-02T12:00:00Z", step="PT6H")
```

Catalog 加载与来源绑定分开；当前内置资源及显式覆盖优先级见 {doc}`/guide/public-query`
和 {doc}`/development/architecture/catalog-and-plugins`。旧 `.resolve().source` 和
`SourceSpec` 不再是公开入口。旧 YAML/Jinja2 data_finder 格式见 {doc}`legacy-api`。
