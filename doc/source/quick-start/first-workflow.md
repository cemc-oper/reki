---
jupytext:
  text_representation: {extension: .md, format_name: myst}
kernelspec: {display_name: Python 3, language: python, name: python3}
---

# 第一个 GRIB 工作流

先按 {doc}`test-data` 下载 IFS 样例。示例获取本地文件路径，用参数名 `t2m` 选择
2 米气温，再从读取结果中裁剪一块区域。

```{code-cell} ipython3
from reki import from_source
from reki.sources import get_source
from reki.operator import extract_region

path = get_source("test", "ecmwf_ifs").mutate().path
with from_source({"kind": "file", "path": str(path)}) as source:
    field = source.sel(parameter="t2m").one()
    assert field.metadata["native_fields"]["shortName"] == "2t"
    t2m = field.to_xarray()["t2m"].squeeze(drop=True)
assert t2m.dims == ("latitude", "longitude")
east_asia = extract_region(t2m, 105, 125, 25, 45)
assert east_asia.shape == (81, 81)
east_asia
```

`one()` 要求唯一匹配，分别用 `no_match` 和 `multiple_matches` 报告缺场与多匹配。
`field.metadata` 可在解码前读取报头，`to_xarray()` 解码后的数组可在来源关闭后继续使用。
参数名、原生键和查询报告的用法见 {doc}`/guide/public-query`。
