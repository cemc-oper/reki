---
jupytext:
  text_representation: {extension: .md, format_name: myst}
kernelspec: {display_name: Python 3, language: python, name: python3}
---

# 公开来源声明

`reki.from_source()` 只接收 source mapping。旧 `SourceSpec`、位置式名称构造及顶层
`from_source_lazily` 已退出。测试文件可由测试资料工具获取，再作为普通 file 来源查询：

```{code-cell} ipython3
from reki import from_source
from reki.sources import get_source

# Test-data acquisition is separate from public query construction.
file_path = get_source("test", "ecmwf_ifs").mutate().path
source = from_source({"kind": "file", "path": str(file_path)})

fields = source.sel().all()
assert len(fields) > 0
source.close()
```

`all()` 扫描原始记录 metadata，保留来源顺序，不提前解码网格。只在 Field 或 Fields
转为 xarray 时加载值。file、local 和 CMADaaS 的已支持声明见 {doc}`/guide/public-query`
及 {doc}`/guide/cmadaas-query`；不能把内部 format/plugin source 工厂当作第二套公共 SDK。

部署根目录和认证放在调用方上下文中，不写进可共享产品资源。来源访问和服务失败使用
`SourceError`；正常无匹配按 `first()`、`one()`、`all()` 各自契约返回或报错。
