# 公开 API 清单

2026-11-09 N09F 更新。顶层 source mapping 与 cedarkit-query v1 是唯一公共查询协议。
旧 SourceSpec / FieldQuery / FieldMetadata / FieldList、旧异常和 one_or_none 已退出；
cfgrib 命名路径与依赖已删除，不提供提示模块或别名。

下表由源码的显式 __all__（根模块为显式惰性导出表）审计。受保护 format 函数保留各自
已有导出；内部 reki.sources 命名工厂、Source / Reader 和插件辅助工具用于格式分派及测试
资料获取，不作为第二套 v1 QuerySource 构造协议，也不承诺旧模型的稳定性。

| 符号 | 导入路径 | API 页 |
| --- | --- | --- |
| `from_source`, `Query`, `Request`, `QueryError`, `SourceError`, `CompletenessError`, `QueryReport`, `QueryExplanation`, `register`, `Source`, `ReaderCapabilities`, `normalize_data_array`, `validate_data_array`, `load_catalog`, `operator` | `reki` | top-level |
| `Source`, `QueryError`, `SourceError`, `normalize_data_array`, `validate_data_array`, `DataArrayContractWarning`, `DataArrayContractError`, `DataArrayContractIssue` | `reki.core` | core |
| `Source`, `LazySource`, `from_source`, `from_source_lazily`, `get_source`, `source_capability`, `register`, `SourceMaker` | `reki.sources` | sources |
| `Reader`, `ReaderCapabilities`, `reader`, `UnknownReader` | `reki.readers` | readers |
| `Catalog`, `LoadedResource`, `SourceConfiguration`, `load_catalog`, `load_context`, `load_resource`, `plan_source_binding` | `reki.catalog` | catalog |
| `load_field_from_file`, `load_fields_from_file`, `fix_level_type`, `load_message_from_file`, `load_messages_from_file` | `reki.format.grib` | legacy |
| `fix_level_type`, `MISSING_VALUE` | `reki.format.grib.common` | legacy |
| `load_message_from_file`, `load_messages_from_file`, `load_field_from_file`, `load_field_from_files`, `load_bytes_from_file`, `create_message_from_bytes`, `create_messages_from_bytes`, `create_data_array_from_message` | `reki.format.grib.eccodes` | legacy |
| `load_bytes_from_file`, `create_message_from_bytes`, `create_messages_from_bytes` | `reki.format.grib.eccodes.bytes` | legacy |
| `extract_region`, `interpolate_grid` | `reki.format.grib.eccodes.operator` | legacy |
| `load_field_from_file` | `reki.format.grads` | legacy |
| `load_field_from_file` | `reki.format.netcdf` | legacy |
| `load_table_from_file`, `load_nwpc_obs_from_file`, `NWPC_OBS_CONFIG` | `reki.format.table` | legacy |

Field / Fields / QuerySource 从公开查询返回，身份、QueryReport 与 QueryExplanation
遵循 v1 schema。xarray Dataset 为公共组织出口；规范名、原生单位与坐标不能混用。
历史 IndexStore 仅为内部残留模块，读取链不访问它。受保护函数的精确行为见
{doc}`/guide/legacy_grib`，source 声明见 {doc}`/guide/public-query`。

`reki request explain/read` 具有当前 v1 原生烟测；历史所有调用方式一致性仍单独跟踪。
`reki inspect/ls/query` 是独立资料探索工具，显式索引启用报 unsupported。
