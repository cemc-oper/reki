# NetCDF

NetCDF reader 使用 xarray 后端打开文件。变量名、维度和坐标通常保留源文件的语义，因而
与 GRIB 的统一 metadata 可能不同；请先查看 `metadata()` 或 xarray 对象再编写处理代码。
可通过 `engine=`、`chunks=` 等 reader 选项选择后端和惰性读取行为。

多变量文件、group 或特殊编码是否可选取取决于 xarray 后端；不支持时不要假定会自动
转换为 GRIB 风格字段。
