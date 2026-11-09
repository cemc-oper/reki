---
jupytext:
  text_representation: {extension: .md, format_name: myst}
kernelspec: {display_name: Python 3, language: python, name: python3}
---

# xarray 输出

Field / Fields 的 `to_xarray()` 返回 Dataset，采用公共维度、坐标、变量分组和报告。
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
适配时出现多变量均明确失败。`cedarkit_query_report` 为执行时 JSON 快照，任意后续
xarray 操作不保证更新或保留它。高频旧读取函数仍返回原生 DataArray，见 {doc}`/guide/legacy_grib`。
