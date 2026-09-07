# 兼容 API：message 级处理

旧 `reki.format.grib.eccodes.operator` 的 `extract_region()` 和
`interpolate_grid()` 面向 ecCodes message。它们与 `reki.operator` 的
`DataArray` 操作不是可互换实现：输入、资源所有权和返回值均可能不同。

新代码先调用 `to_xarray()`，再使用 {doc}`new-api`。仅在维护依赖 message 的旧代码时，
参考 {doc}`/guide/legacy_grib` 中的兼容示例。
