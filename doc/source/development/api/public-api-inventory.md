---
orphan: true
---

# 公开 API 清单

> T0-2 基线，2026-09-07。此清单定义 T4 API 参考的审计范围，而不是由 autodoc
> 根据名称自动发现的列表。`推荐` 表示新的规范导入路径；`兼容` 表示项目仍承诺的旧路径；
> `实验性`/`待确认` 必须经维护者确认后才承诺长期兼容。

“目标页面”是目标信息架构中的页面，T4 创建后应将每个条目链接到实际锚点。测试列是
现有覆盖证据或应补的最小示例，不能代替 API 文档。

## 判定规则

1. 顶层及子包 `__all__` 是明确的受支持导出；顶层重导出以 `reki.__all__` 为准。
2. 旧 `reki.data_finder` 和 `reki.format.*` 的显式导出属于兼容面。
3. 具有面向用户命令或被公开工厂/模块明确返回的类，列为推荐或待确认；仅仅未以下划线开头不足以成为公开 API。
4. `reki.readers.grib.index` 明确自称 internal，即使有 `__all__` 也不加入长期公开 API；其功能应在架构页说明。

## 顶层 `reki`

| 符号 | 规范导入路径 | 稳定性 | 目标页面 | 证据 |
| --- | --- | --- | --- | --- |
| `from_source`, `from_source_lazily`, `register`, `source_capability`, `Source` | `reki` | 推荐 | `development/api/top-level.md`、`sources.md` | `tests/sources/test_from_source.py`、`test_source_maker.py`、`test_lazy.py` |
| `SourceSpec`, `FieldQuery`, `FieldMetadata`, `FieldList` | `reki` | 推荐 | `top-level.md`、`core.md` | `tests/core/test_source_spec.py`、`test_field_query.py`、`test_field_list_core.py` |
| `ReaderCapabilities` | `reki` | 推荐 | `top-level.md`、`readers.md` | `tests/readers/test_readers.py` |
| `DataNotFoundError`, `MultipleFieldsMatchedError`, `UnsupportedOperationError` | `reki` | 推荐 | `top-level.md`、`core.md` | `tests/readers/test_grib_cardinality.py`、`test_readers.py` |
| `normalize_data_array`, `validate_data_array` | `reki` | 推荐 | `top-level.md`、`core.md` | `tests/core/test_xarray_contract.py` |
| `load_catalog` | `reki` | 推荐 | `top-level.md`、`catalog.md` | `tests/catalog/test_catalog.py` |
| `CmadaasRequest`, `CmadaasRequestError`, `CmadaasNameNotMappedError`, `CmadaasRequestConflictError`, `bind_cmadaas_request` | `reki` | 推荐 | `top-level.md`、`cmadaas.md` | `tests/test_cmadaas_request.py` |
| `ExternalNameResolution`, `ParameterAmbiguityError`, `ParameterConditionConflictError`, `ParameterExternalNameNotMappedError`, `ParameterNamespaceNotFoundError`, `ParameterNotFoundError`, `ParameterRecord`, `ParameterResolutionError`, `ResolvedParameter`, `resolve_external_name`, `resolve_parameter` | `reki` | 推荐 | `top-level.md`、`grib.md` | `tests/core/test_parameter_resolver.py`、`tests/readers/grib/test_param_registry.py` |
| `operator` | `reki.operator` | 推荐（模块） | `development/api/operators.md` | `tests/operator/test_module_boundary.py` |

## 核心模型与来源

| 符号 | 规范导入路径 | 稳定性 | 目标页面 | 证据 |
| --- | --- | --- | --- | --- |
| `Source`, `SourceSpec`, `FieldQuery`, `FieldMetadata`, `FieldList` | `reki.core` | 推荐 | `development/api/core.md` | `tests/core/test_source_spec.py`、`test_field_query.py`、`test_field_list_core.py` |
| `QueryError`, `DataNotFoundError`, `MultipleFieldsMatchedError`, `UnsupportedOperationError` | `reki.core` | 推荐 | `core.md` | `tests/core/test_field_query.py`、`tests/readers/test_grib_cardinality.py` |
| `normalize_data_array`, `validate_data_array`, `DataArrayContractWarning`, `DataArrayContractError`, `DataArrayContractIssue` | `reki.core` | 推荐 | `core.md` | `tests/core/test_xarray_contract.py` |
| `Source`, `LazySource`, `SourceMaker`, `from_source`, `from_source_lazily`, `get_source`, `source_capability`, `register` | `reki.sources` | 推荐 | `development/api/sources.md` | `tests/sources/test_from_source.py`、`test_source_maker.py`、`test_lazy.py` |
| `TestSource`, `FileSource`, `FilePatternSource`, `LocalSource`, `UrlSource`, `MemorySource`, `CmadaasSource` | `reki.sources.test`, `.file`, `.file_pattern`, `.local`, `.url`, `.memory`, `.cmadaas` | 推荐的内置 source 类型 | `sources.md` | 相应 `tests/sources/test_*.py` |
| `SourceCapability` | `reki.sources.cmadaas` | 待确认（未由包重导出） | `sources.md`、`cmadaas.md` | `tests/sources/test_cmadaas.py` |

## 读取器与 GRIB

| 符号 | 规范导入路径 | 稳定性 | 目标页面 | 证据 |
| --- | --- | --- | --- | --- |
| `Reader`, `ReaderCapabilities`, `reader`, `UnknownReader` | `reki.readers` | 推荐 | `development/api/readers.md` | `tests/readers/test_readers.py`、`test_other_readers.py` |
| `GribReader`, `GribField`, `load_fields_from_file`, `fix_level_type`, `load_message_from_file`, `load_messages_from_file` | `reki.readers.grib` | 推荐 | `readers.md`、`grib.md` | `tests/readers/test_grib.py`、`test_grib_query.py`、`test_grib_lazy.py` |
| `GradsReader`, `load_field_from_file` | `reki.readers.grads` | 推荐 | `readers.md` | `tests/format/grads/test_lazy.py` |
| `NetCDFReader`, `load_field_from_file` | `reki.readers.netcdf` | 推荐 | `readers.md` | `tests/format/netcdf/test_lazy.py` |
| `TableReader`, `load_table_from_file`, `load_nwpc_obs_from_file`, `NWPC_OBS_CONFIG` | `reki.readers.table` | 推荐 | `readers.md` | `tests/readers/test_other_readers.py` |
| `CmadaasReader` | `reki.readers.cmadaas` | 待确认（未由 `reki.readers` 重导出） | `readers.md`、`cmadaas.md` | `tests/readers/test_cmadaas_reader.py` |
| `ExternalNameResolution`, `GribParameterKey`, `ParameterAmbiguityError`, `ParameterConditionConflictError`, `ParameterExternalNameNotMappedError`, `ParameterIndex`, `ParameterNamespaceNotFoundError`, `ParameterNotFoundError`, `ParameterRecord`, `ParameterResolutionError`, `ResolvedParameter`, `WHEN_KEYS`, `check_value`, `find_cemc_name`, `find_parameter_record`, `find_short_name`, `find_wgrib2_name`, `get_param_registry`, `get_parameter_index`, `resolve_external_name`, `resolve_parameter` | `reki.readers.grib.config` | 推荐 | `development/api/grib.md` | `tests/core/test_parameter_resolver.py`、`tests/readers/grib/test_param_registry.py` |
| `INDEX_SCHEMA_VERSION`, `IndexBuildError`, `IndexStore`, `SourceFingerprint`, `fingerprint_file`, `index_path_for` | `reki.readers.grib.index` | 内部实现（不生成长期 API 页） | `development/architecture/grib-reader-and-index.md` | `tests/readers/grib/test_index_store.py` |

## catalog、operators、diagnostics 与 CMADaaS

| 符号 | 规范导入路径 | 稳定性 | 目标页面 | 证据 |
| --- | --- | --- | --- | --- |
| `Catalog`, `CatalogError`, `DatasetRecord`, `ResolvedDataset`, `load_catalog` | `reki.catalog` | 推荐 | `development/api/catalog.md` | `tests/catalog/test_catalog.py` |
| `extract_region`, `sample_nearest`, `extract_point`, `interpolate_grid` | `reki.operator` | 推荐 | `development/api/operators.md` | `tests/operator/test_extract_region.py`、`test_sample_nearest.py`、`test_extract_point.py`、`test_interpolate_grid.py` |
| `collect_io_metrics`, `IOMetrics`, `IOMetricsSnapshot` | `reki.diagnostics` | 实验性（模块无 `__all__`，需维护者确认） | `development/api/diagnostics.md` | `tests/diagnostics/test_io_metrics.py` |
| `CmadaasRequest`, `CmadaasRequestError`, `CmadaasNameNotMappedError`, `CmadaasRequestConflictError`, `bind_cmadaas_request` | `reki.cmadaas_request` | 推荐 | `development/api/cmadaas.md` | `tests/test_cmadaas_request.py` |
| `build_inventory`; CLI command `cmadaas-inventory` | `reki.cmadaas_inventory`；`reki cmadaas-inventory` | 待确认（命令已注册，Python helper 未重导出） | `cmadaas.md` | `tests/test_cmadaas_inventory.py` |

## 兼容层

| 符号 | 规范导入路径 | 稳定性 | 目标页面 | 证据 |
| --- | --- | --- | --- | --- |
| `find_local_file`, `find_local_files`, `get_local_file_name` | `reki.data_finder` | 兼容 | `development/api/legacy.md` | `tests/integration/cma_hpc/data_finder/`（环境专属）；指南示例 |
| `load_field_from_file`, `load_fields_from_file`, `fix_level_type`, `load_message_from_file`, `load_messages_from_file` | `reki.format.grib` | 兼容 | `legacy.md` | `tests/format/grib/` |
| `load_field_from_file`, `load_fields_from_file` | `reki.format.grib.cfgrib` | 兼容 | `legacy.md` | `tests/format/grib/` |
| `fix_level_type`, `convert_parameter`, `MISSING_VALUE` | `reki.format.grib.common` | 兼容 | `legacy.md` | `tests/format/grib/` |
| `load_message_from_file`, `load_messages_from_file`, `load_field_from_file`, `load_field_from_files`, `load_bytes_from_file`, `create_message_from_bytes`, `create_messages_from_bytes`, `create_data_array_from_message` | `reki.format.grib.eccodes` | 兼容 | `legacy.md` | `tests/format/grib/eccodes/` |
| `load_bytes_from_file`, `create_message_from_bytes`, `create_messages_from_bytes` | `reki.format.grib.eccodes.bytes` | 兼容 | `legacy.md` | `tests/format/grib/eccodes/` |
| `extract_region`, `interpolate_grid` | `reki.format.grib.eccodes.operator` | 兼容 | `legacy.md` | `tests/operator/test_module_boundary.py` |
| `load_field_from_file` | `reki.format.grads`、`reki.format.netcdf` | 兼容 | `legacy.md` | `tests/format/grads/test_lazy.py`、`tests/format/netcdf/test_lazy.py` |
| `load_table_from_file`, `load_nwpc_obs_from_file`, `NWPC_OBS_CONFIG` | `reki.format.table` | 兼容 | `legacy.md` | `tests/readers/test_other_readers.py` |
| `GribParameterKey`, `check_value`, `get_param_registry`, `find_parameter_record`, `find_short_name`, `find_wgrib2_name`, `find_cemc_name` | `reki.format.grib.config` | 兼容 | `legacy.md` | `tests/readers/grib/test_param_registry.py` |

## CLI

| 命令 | 稳定性 | 目标页面 | 证据 |
| --- | --- | --- | --- |
| `reki catalog list`, `reki catalog show DATASET_ID`, `reki catalog resolve DATASET_ID` | 推荐 | `development/api/catalog.md` | `tests/test_cli.py`、`tests/catalog/test_catalog.py` |
| `reki inspect PATH`, `reki ls PATH`, `reki query PATH` | 推荐 | `development/api/readers.md`、`grib.md` | `tests/test_cli.py` |
| `reki cmadaas-inventory --manifest PATH --root PATH --output PATH` | 待确认 | `development/api/cmadaas.md` | `tests/test_cmadaas_inventory.py` |
| `reki-finder` | 兼容 | `development/api/legacy.md` | 缺少独立 CLI 测试；T4/T5 补充 |
| `reki-test-data download DATASET` | 推荐的测试数据工具 | `quick-start/test-data.md` | `tests/sources/test_test_source.py` |

## 已识别的公开路径缺口

1. `reki.data_finder`、`reki.operator`、`reki.diagnostics` 以及多个 reader 子包没有 `__all__`；本清单只采纳其显式导出和已有公开调用点，不能把模块扫描结果视为承诺。
2. `CmadaasReader`、`SourceCapability`、`build_inventory` 有测试或 CLI/源代码调用点，但未从各自的顶层公共包重导出。维护者应在 T4 前确定是补充规范导出还是将其标为内部。
3. `reki.readers.grib.index` 有 `__all__`，但模块 docstring 明确标记为 internal；应只从架构页链接，不作为扩展 API 承诺。
4. 现有 `develop/api/grib.rst` 引用的 `reki.format.grib.eccodes` 是兼容路径；T4 应改用本清单中的 `reki.readers.grib` 规范路径，并另在 `legacy.md` 保留兼容说明。
