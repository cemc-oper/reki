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

# 打开本地文件

当调用方已经拥有一个确定路径时，用 `file` source。下面从冻结 IFS 文件开始，完整地
选择并加载 2 米温度；这与快速开始的 `test` source 得到相同的 reader，只是路径由调用
方负责。

```{code-cell} ipython3
import os
from pathlib import Path

from reki import from_source

path = Path(os.environ["REKI_TEST_DATA_DIR"]) / "ifs_eastasia_2026090712_f024.grib2"
reader = from_source("file", path)
field = reader.sel(parameter="2t", level_type="heightAboveGround", level=2).first()
assert field is not None
data = field.to_xarray()
assert data.shape == (241, 361)
data.name, data.dims
```

`file` 不会展开 glob，也不猜测时次。若路径不存在，先检查 `Path(path).is_file()`；不要把
不存在的路径误当作零匹配字段。

对于多个已有文件，用 `file-pattern` 明确描述文件名模板和时次。该 source 只渲染路径，
直到读取器被访问才打开文件：

```python
from reki import from_source

reader = from_source(
    "file-pattern", "/srv/ifs/{start_time_label}", "ifs_f{forecast_hour_label}.grib2",
    start_time="2026090712", forecast_time="24h",
)
```

模板只支持受限的起报和时效字段；实际文件布局与命名由部署决定。多个文件的字段合并和
基数规则见 {doc}`/guide/grib/multiple-fields`。
