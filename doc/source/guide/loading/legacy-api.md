# 兼容 API：reki.format

`reki.format.grib`、`grads`、`netcdf` 和 `table` 的入口继续支持旧代码，但新代码应统一
使用 `from_source()`、`sel()` 和相应的转换。旧函数常直接返回 `DataArray`、`DataFrame`
或 `None`，资源所有权和多字段语义与 reader API 不同。

完整 GRIB 兼容示例（包括 ecCodes message 访问）见 {doc}`/guide/legacy_grib`；迁移对照
见 {doc}`/guide/migration`。
