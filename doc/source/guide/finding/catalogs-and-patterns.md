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

`local` 把产品、起报时间、时效和成员交给部署的 catalog 解析。先加载自己的 catalog，
再把得到的 `SourceSpec` 交给 `from_source()`；catalog 解析本身不会扫描业务文件：

```python
from reki import from_source, load_catalog

resolved = load_catalog(user_path="/etc/reki/catalog.yaml").resolve("my_ifs")
reader = from_source(resolved.source)
```

不要把 `/etc`、挂载目录或组织内产品名写入可共享 notebook。若只需要按固定布局查找本地
文件，优先使用 {doc}`local-files` 的 `file-pattern`，它无需 catalog 配置。
