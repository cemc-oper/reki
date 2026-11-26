---
jupytext:
  text_representation: {extension: .md, format_name: myst}
kernelspec: {display_name: Python 3, language: python, name: python3}
---

# xarray 输出

Selection / Field / Fields 的 `to_xarray()` 返回 Dataset，采用公共维度、坐标和变量分组。
原生字段没有业务转换；单变量可显式改名，并在算子边界取 DataArray。

```{code-cell} ipython3
from reki import from_source
from reki.sources import get_source

# Test-data acquisition is separate from public query construction.
file_path = get_source("test", "ecmwf_ifs").mutate().path
source = from_source({"kind": "file", "path": str(file_path)})

dataset = source.sel(native={"grib": {"shortName": "2t"}}, level_type="height_above_ground", level=2).one().to_xarray(rename="t2m")
data = dataset.t2m.squeeze(drop=True)
assert data.dims == ("latitude", "longitude")
assert data.attrs["units"] == "K"
source.close()
```

相同变量内部缺口可填 NaN，完全不存在的坐标不补造。重复位置、不同网格或单变量
适配时出现多变量均明确失败。高频旧读取函数返回原生 DataArray，见 {doc}`/guide/legacy_grib`。

`include_report` 默认为 `False`。传入 `include_report=True` 时，Dataset 和每个数据变量的
`attrs["cedarkit_query_report"]` 保存同一份执行报告的 JSON 快照。快照对应原始查询，后续
xarray 操作按各自的属性保留规则处理它。报告也可通过 Field 或 Fields 的 `.report` 读取。
