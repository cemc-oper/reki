# 发布说明

## 未发布

- `reki.format.grib.load_field_from_file()` 的 `level_type="pl"` 保留原生层坐标。该入口与 `reki.format.grib.eccodes.load_field_from_file()` 均提供旧绘图属性，并附加报文中的单位。
- `reki.format.grib.eccodes.load_field_from_files(level=None)` 每文件取首个匹配场。显式选层采用公共维度，`level_dim` 和 `lazy=True` 报 `unsupported`。零匹配返回 `None`。见 {ref}`migration-grib-collections`。
- `reki.format.grib.load_fields_from_file()` 使用 ecCodes 和按 GRIB 键生成的变量名。气压层 Dataset 使用 `time`、`step`、`pressure` 和空间维度，字段以原生解码精度返回。旧变量名、维度和精度的转换见 {ref}`migration-grib-collections`。
- `reki.format.grib` 及其 `eccodes` 模块的 `load_message_from_file()` 和 `load_messages_from_file()` 要求一基整数 `count`。`reki.format.grib.eccodes.load_bytes_from_file()` 支持按序号读取，零匹配返回 `None`。读取字节及消息筛选或字段解码失败时会释放入口拥有的 ecCodes 句柄。见 {ref}`migration-grib-messages`。
- `reki.format.netcdf.load_field_from_file()` 缺变量或层值报 `QueryError`（`no_match`）。该入口和 `reki.format.grads.load_field_from_file()` 缺文件时报 `SourceError`（`resource_not_found`），惰性 GrADS 二进制文件错误在取值时报出。见 {ref}`migration-format-errors`。
- `reki.format.grads.load_field_from_file()` 的 `forecast_time` 坐标使用选中记录的时效。见 {ref}`migration-grads-time`。
