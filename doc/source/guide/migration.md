# 新旧 API 迁移

公开 source 构造使用 mapping，Query / Request 和错误来自唯一 v1 契约。
SourceSpec / FieldQuery / FieldList / FieldMetadata、旧异常及 one_or_none 已退出。

| 旧调用 | 当前入口与差异 |
| --- | --- |
| from_source("file", path) | from_source({"kind": "file", "path": path})；来源由上下文管理。 |
| SourceSpec / 旧查询模型 | 声明式来源 + Query / Request；不保留模型别名或转换窗口。 |
| one_or_none | 捕获 one() 的 no_match；多匹配仍报错。 |
| cfgrib / 其命名路径 | 已删除；显式 engine="cfgrib" 报 unsupported。 |
| with_index | False 无提示；True / 路径 FutureWarning 一次，路径零访问。 |
| 高频 load_field_from_file | 继续保护原生首匹配／文件顺序／单位／lazy，不等同公共 Dataset。 |
| 低频 load_field_from_files / load_fields_from_file | 返回 DataArray 或 None / Dataset，采用公共维度组织，可选附加查询报告。 |
| NetCDF / GrADS | 保留原生格式函数及其惰性，不声明公共 Query 已支持所有格式。 |
| 原生消息／字节 | 保留 count、顺序和句柄所有权；不以 DataArray 替代原报文操作。 |

完整工作流见 {doc}`/quick-start/first-workflow`，原生条件与公共输出见
{doc}`public-query`，旧函数的精确保护范围见 {doc}`legacy_grib`。

## 读取与导出查询报告

通过 `Field.report` 或 `Fields.report` 读取查询报告。`to_xarray()` 默认省略
`cedarkit_query_report` 属性。需要将报告随 xarray 结果保存时，传入 `include_report=True`。

```python
report = field.report
dataset = field.to_xarray(include_report=True)
```

使用 CLI 写 NetCDF 时，通过 `--include-report` 将报告写入文件的属性。

```bash
reki request read --include-report request.json output.nc
```

报告属性的位置与格式见 {doc}`grib/xarray-output`，CLI 用法见 {doc}`query-cli`。

## 内容覆盖矩阵

| 概念 | 用户页面 | 实现/API 页面 |
| --- | --- | --- |
| source、catalog、远程惰性 | {doc}`finding/index` | {doc}`/development/api/sources`、{doc}`/development/architecture/source-reader-pipeline` |
| 查询、metadata、字段列表 | {doc}`grib/open-and-inspect`、{doc}`grib/select-fields` | {doc}`/development/architecture/query-model` |
| xarray 输出与输入契约 | {doc}`grib/xarray-output`、{doc}`processing/index` | {doc}`/development/architecture/xarray-contract` |
| GRIB 参数、层次与 index | {doc}`grib/index` | {doc}`/development/api/grib`、{doc}`/development/architecture/grib-reader-and-index` |
| 兼容入口 | 各分区 `legacy-api` 页面 | {doc}`/development/api/legacy` |

## 旧链接映射

现有 URL 继续作为兼容页保留，避免外部深链接立即失效；新内容应链接到下表的目标页。

| 旧 URL | 唯一正文 / 推荐目标 | 保留方式 |
| --- | --- | --- |
| `getting-started/index` | {doc}`/quick-start/index` | 兼容页 |
| `getting-started/installing` | {doc}`/quick-start/installation` | 兼容页 |
| `getting-started/test-data` | {doc}`/quick-start/test-data` | 兼容页 |
| `getting-started/quick-overview` | {doc}`/quick-start/first-workflow` | 兼容页 |
| `guide/data_find` | {doc}`finding/index` | 兼容页 |
| `guide/catalog` | {doc}`finding/catalogs-and-patterns` | 兼容页 |
| `guide/data_load` | {doc}`grib/index` 与 {doc}`loading/index` | 兼容页 |
| `guide/data_process` | {doc}`processing/index` | 兼容页 |
| `guide/loading/exploring-data` | {doc}`grib/open-and-inspect` | 兼容页 |
| `guide/loading/new-api` | {doc}`grib/select-fields` | 兼容页 |
| `guide/loading/xarray-output` | {doc}`grib/xarray-output` | 兼容页 |
| `guide/loading/grib` | {doc}`grib/index` | 兼容页 |
| `guide/grib_parameter` | {doc}`grib/parameters` | 兼容页 |
| `guide/grib_level` | {doc}`grib/levels` | 兼容页 |
| `guide/legacy_find`、`guide/legacy_finder_config` | 旧 `data_finder` 正文 | 兼容 API 的唯一正文；从 {doc}`finding/legacy-api` 进入 |
| `guide/legacy_grib` | 旧 `reki.format.grib` 正文 | 兼容 API 的唯一正文；从 {doc}`loading/legacy-api` 与 {doc}`processing/legacy-api` 进入 |

兼容页只解释迁移目的并链接唯一正文，不复制参数、数据版本、示例或实现细节。任何新增用户
教程都必须链接上表中的目标页；只有旧 API 维护说明继续在 `legacy_*` 页面保留正文。
