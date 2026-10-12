# 数据加载

GRIB reader 支持 `sel()`、`first()`、`all()` 和元数据探索；其他格式应按各自的
reader 能力调用转换方法。NetCDF 直接使用 `to_xarray()`，表格主要使用
`to_pandas()`，GrADS 可用 `sel()` 与 `to_xarray()`。公共 `reki request` 的本地
字段定位和集合读取只支持 GRIB；将这些其他文件交给该入口会报 `unsupported`，
不会返回未筛选的数据。

```{toctree}
:maxdepth: 1

new-api
exploring-data
xarray-output
grib
grads
netcdf
table
legacy-api
```
