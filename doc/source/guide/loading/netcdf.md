# NetCDF

受保护函数使用 xarray 后端，保留变量名、坐标、单位和原生惰性存储；不强加公共 GRIB
维度组织或报告。可以传 engine / chunks 等 xarray 选项。

```python
from reki.readers.netcdf import load_field_from_file

field = load_field_from_file("forecast.nc", parameter="temperature", level_type="level", level=850)
try:
    values = field.values
finally:
    field.close()
```

parameter=None 取第一个数据变量；无数据变量、缺变量或层值报 QueryError(no_match)。
显式 level_type 指定的坐标不存在时为 invalid_query。成功字段携带 Dataset.close 回调，
选择失败立即关闭 Dataset；调用方任意第三方操作不由 reki 拦截改写异常。
