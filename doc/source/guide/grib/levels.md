---
jupytext:
  text_representation: {extension: .md, format_name: myst}
kernelspec: {display_name: Python 3, language: python, name: python3}
---

# 层次

公共压力坐标使用 `level_type="pressure"` 与 hPa 层值；离地高度使用
`height_above_ground` 与米。旧 `pl/isobaricInhPa` 别名只在受保护读取函数中适配。

```{code-cell} ipython3
from reki import from_source
from reki.sources import get_source

# Test-data acquisition is separate from public query construction.
file_path = get_source("test", "ecmwf_ifs").mutate().path
source = from_source({"kind": "file", "path": str(file_path)})

fields = source.sel(native={"grib": {"shortName": "t"}}, level_type="pressure", level=[500, 850]).all()
dataset = fields.to_xarray(rename="temperature")
assert dataset.pressure.values.tolist() == [850, 500]
source.close()
```

层状字段使用公共 layer 的上下端点身份，不能用单个标量层值代替。原始表面类型、缩放
因子和值保存在 native_fields；来源未知时可直接按编码键选场，不猜规范层次。
高频函数保留文件顺序和 level_dim；低频集合函数采用这里的公共组织规则。
