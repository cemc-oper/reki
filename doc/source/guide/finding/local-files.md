# 打开本地文件

路径由调用方显式提供，不需要先登记具名参数或产品。单文件、文件列表与有序 glob
均是公开 file 来源的候选范围；元数据与原始参数键用于区别实际报文。

```python
from reki import from_source

with from_source({"kind": "file", "path": "/data/original.grib2"}) as source:
    field = source.sel(native={"grib": {"shortName": "2t"}}, level_type="height_above_ground", level=2).one()
    data = field.to_xarray(rename="t2m").t2m.squeeze(drop=True)
```

来源不存在报 SourceError(resource_not_found)，不能当作正常无匹配。local 来源的目录
模板、时次和成员发现由 dataset 的已登记布局负责，部署 root 属于上下文，不写进业务
资源。来源范围、重复与公共组织见 {doc}`/guide/public-query`。
