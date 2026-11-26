---
jupytext:
  text_representation: {extension: .md, format_name: myst}
kernelspec: {display_name: Python 3, language: python, name: python3}
---

# 层次

公共压力坐标使用 `level_type="pressure"`，默认单位为 hPa。离地高度使用
`height_above_ground` 与米。`isobaricInhPa` 可在旧式 GRIB 读取函数中用作 ecCodes 层类型。

Python `source.sel()` 接受 `pl`、`sfc` 和 `ml`，对应 `pressure`、`surface` 和
`model_level`。直接构造 Query 或编写 JSON/YAML Request 时使用规范名称。

地面层可以省略 `level`，也支持旧写法 `level_type="sfc", level=0`。模式层使用非负整数编号，
例如 `level_type="ml", level=20`。CMA MODELVAR 中固定面编码为 131 的报文可按原生 GRIB 键
查询，也可使用旧式 GRIB 读取函数。

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
