# 新旧 API 迁移

新代码使用 `from_source()`、查询对象和统一转换；兼容 API 不会在本页以外的推荐示例中
出现。迁移应先固定 source 与查询语义，再比较返回类型和资源所有权。

| 旧入口 | 推荐替代项 | 迁移注意事项 |
| --- | --- | --- |
| `find_local_file()` / `find_local_files()` | `from_source("local", ...)` | 旧函数返回路径；新入口返回 reader 或 source。 |
| `get_local_file_name()` | `SourceSpec` / local 配置解析 | 仅需渲染路径时可保留旧函数；不要为此读取文件。 |
| `reki.format.grib.load_field_from_file()` | `from_source("file", path).sel(...).first().to_xarray()` | 明确处理无匹配、多匹配和懒解码。 |
| `reki.format.grads/netcdf.load_field_from_file()` | `from_source("file", path)` 加 `sel()` / 转换 | 检查变量、层次与 xarray 输出差异。 |
| `reki.format.table.*` | `from_source("file", path).to_pandas()` | 表格不承诺 xarray 输出。 |
| ecCodes message 操作 | `to_xarray()` 后的 `reki.operator` | message 和 DataArray 的资源与坐标语义不同。 |

## GRIB 读取：完整代码对照

旧入口直接接收文件路径，且调用方通常同时承担参数、层次与返回值的解释。它只应存在于
维护兼容代码的场景：

```python
from reki.format.grib import load_field_from_file

legacy_field = load_field_from_file("/data/forecast.grib2", parameter="2t")
```

新入口把来源、查询和数值转换拆开。每一步都可单独记录和测试；`first()` 的空结果必须
显式处理，避免把“不存在的字段”误报为解码故障：

```python
from reki import from_source

reader = from_source("file", "/data/forecast.grib2")
field = reader.sel(
    parameter="2t", level_type="heightAboveGround", level=2,
).first()
if field is None:
    raise LookupError("未找到 2 米温度；请检查参数、层次和时效")
data = field.to_xarray()
```

## 处理：message 操作迁移到带坐标的数组

旧的 ecCodes message 操作围绕原始 GRIB message；新工作流在 `DataArray` 上操作，因此
区域范围、坐标名和输出维度可见并可由 xarray 检查：

```python
from reki.operator import extract_region

east_asia = extract_region(
    data,
    start_longitude=105,
    end_longitude=125,
    start_latitude=25,
    end_latitude=45,
)
```

迁移测试应至少断言：同一来源与查询条件得到预期字段、输出包含 `latitude`/`longitude`，
以及空查询、文件缺失和不满足坐标契约时产生明确异常。

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
| `guide/grib_parameter`、`guide/parameter_resolver` | {doc}`grib/parameters` | 兼容页 |
| `guide/grib_level` | {doc}`grib/levels` | 兼容页 |
| `guide/legacy_find`、`guide/legacy_finder_config` | 旧 `data_finder` 正文 | 兼容 API 的唯一正文；从 {doc}`finding/legacy-api` 进入 |
| `guide/legacy_grib` | 旧 `reki.format.grib` 正文 | 兼容 API 的唯一正文；从 {doc}`loading/legacy-api` 与 {doc}`processing/legacy-api` 进入 |

兼容页只解释迁移目的并链接唯一正文，不复制参数、数据版本、示例或实现细节。任何新增用户
教程都必须链接上表中的目标页；只有旧 API 维护说明继续在 `legacy_*` 页面保留正文。
