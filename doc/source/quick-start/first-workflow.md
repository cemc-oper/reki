---
jupytext:
  text_representation: {extension: .md, format_name: myst}
kernelspec: {display_name: Python 3, language: python, name: python3}
---

# 第一个 GRIB 工作流

先按 {doc}`test-data` 准备冻结 IFS 文件。测试资料工厂只负责取本地资产，公开查询使用
声明式 file 来源；metadata 与值读取分开。

```{code-cell} ipython3
from reki import from_source
from reki.sources import get_source
from reki.operator import extract_region

path = get_source("test", "ecmwf_ifs").mutate().path
with from_source({"kind": "file", "path": str(path)}) as source:
    records = source.sel().all()
    assert len(records) > 0
    headers = [dict(field.metadata["native_fields"]) for field in records]
    assert any(header["shortName"] == "2t" for header in headers)
    selected = source.sel(native={"grib": {"shortName": "2t"}}, level_type="height_above_ground", level=2)
    t2m = selected.one().to_xarray(rename="t2m").t2m.squeeze(drop=True)
    assert source.sel(native={"grib": {"parameterNumber": 250}}).first() is None
assert t2m.dims == ("latitude", "longitude")
east_asia = extract_region(t2m, 105, 125, 25, 45)
assert east_asia.shape == (81, 81)
east_asia
```

`one()` 要求唯一字段；无匹配与多匹配是不同 QueryError。Dataset 在来源关闭前完成解码，
取出的内存 DataArray 可在关闭后继续用于算子。没有独立业务预期域时报告为 unchecked，
不能因本地文件可读就宣称业务完整。详细查询与格式边界见 {doc}`/guide/public-query`、
{doc}`/guide/migration` 和 {doc}`/guide/legacy_grib`。
