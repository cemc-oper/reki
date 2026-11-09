# 惰性读取

公共 `all()` / `one()` 扫描头并定位记录，不提前解码值；Field / Fields 转 xarray 时生成
独立内存 Dataset。来源关闭前完成转换，不把公共组织误认为旧的 lazy=True DataArray。

受保护高频函数保留按需解码：

```python
from reki.readers.grib.eccodes import load_field_from_file

array = load_field_from_file("original.grib2", parameter="t", level_type="pl", level="all", lazy=True)
# isel / sel 保持惰性；values 只解码所选报文，原文件必须仍可读。
values = array.isel(pl=0).values
```

这里不需要额外的来源上下文。两个低频集合函数返回独立内存结果；多文件 lazy=True
明确报 unsupported。NetCDF / GrADS 的原生惰性与关闭规则见各格式页。
