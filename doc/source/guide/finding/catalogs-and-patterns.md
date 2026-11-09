# Catalog 与来源范围

公开来源以 file / local / cmadaas 声明绑定目录资源。file 可直接读取未登记的原生报文；
具名查询需要可执行绑定和明确原生条件，不能从稳定名称猜原场。数据集、参数、来源
布局与部署上下文独立配置，见 {doc}`/guide/public-query` 与
{doc}`/development/architecture/catalog-and-plugins`。

```python
from reki import load_catalog, from_source

catalog = load_catalog()
with from_source({"kind": "file", "path": ["/data/a.grib2", "/data/b.grib2"]}) as source:
    selected = source.sel(native={"grib": {"shortName": "t"}})
```

Catalog 加载只核资源；实际扫描在查询中发生，服务在值读取时请求。旧 ResolvedDataset /
SourceSpec / .resolve().source 入口已退出。原 YAML/Jinja2 路径渲染函数属于受保护
历史工具，不代表公共 Query 接受旧 file-pattern 构造参数。
