---
jupytext:
  text_representation:
    extension: .md
    format_name: myst
    format_version: 0.13
kernelspec:
  display_name: Python 3
  language: python
  name: python3
---

# 使用内存对象、catalog 与路径模板

`memory` source 适合已经在内存中的 NumPy、pandas 或 xarray 对象。它不执行文件或网络
I/O，因此可用于验证后续流程的输入边界：

```{code-cell} ipython3
import numpy as np

from reki import from_source

memory = from_source("memory", np.arange(4))
array = memory.to_xarray()
assert array.dims == ("dim_0",)
assert array.values.tolist() == [0, 1, 2, 3]
array
```

阶段 1.1 的目录格式为 `cedarkit.catalog/v1`，通过显式本地资源引用加载：

```python
from reki.catalog import load_catalog

catalog = load_catalog({"path": "/deployment/catalog.json", "version": "1"})
```

该例只加载配置，不扫描资料或调用服务。当前内置目录仅登记数据集身份／别名，没有可执行产品；真实业务版本、提供范围及来源绑定仍待证据补齐。`load_catalog()` 不再搜索插件或用户目录，也不返回旧 `ResolvedDataset`／`SourceSpec`。运行来源和 CLI 的同步消费由 I05／I08 承接，此处不提供尚未实现的执行示例。

`file` 的字面文件列表、有序 glob 与 `local` 的根目录模板由来源配置负责；参数与产品目录不保存部署根路径或认证。构造／资源优先级和未完成边界见 {doc}`/development/architecture/catalog-and-plugins`，API 见 {doc}`/development/api/catalog`。
