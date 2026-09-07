# xarray 输出

`to_xarray()` 返回 `xarray.DataArray` 或格式适用时的 `Dataset`。用户可依赖的观察约定
包括空间坐标 `latitude` / `longitude`、可用的时间坐标（`time`、`step`、`valid_time`）、
层次坐标以及来源属性；具体字段、缺测值和维度仍由格式决定。

`to_numpy()` 适合只需要数值的场景；`to_pandas()` 适合表格或一维/二维数据。若 reader
不支持某项转换，会抛出 `UnsupportedOperationError`，而不会静默改变输出类型。处理操作
要求的坐标与维度见 {doc}`/guide/processing/new-api`；严格规范化与验证属于开发文档。
