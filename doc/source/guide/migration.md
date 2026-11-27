---
jupytext:
  text_representation: {extension: .md, format_name: myst}
kernelspec: {display_name: Python 3, language: python, name: python3}
---

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
| load_field_from_files / load_fields_from_file | 多文件 `level=None` 逐文件取首场。显式选层和单文件 Dataset 使用公共维度，可选附加查询报告。 |
| NetCDF / GrADS | 保留原生格式函数及其惰性，不声明公共 Query 已支持所有格式。 |
| 原生消息／字节 | 保留 count、顺序和句柄所有权；不以 DataArray 替代原报文操作。 |

完整工作流见 {doc}`/quick-start/first-workflow`，原生条件与公共输出见
{doc}`public-query`，旧函数的精确保护范围见 {doc}`legacy_grib`。

(migration-grib-collections)=
## GRIB 集合读取

`load_field_from_files(level=None)` 按每个文件的报文顺序取首个匹配场。
常规经纬度单场保留 `(time, step, latitude, longitude)` 和标量层坐标。
用 `level="all"` 或层值列表请求多层。显式选层采用公共坐标，气压层使用
`pressure`，即使只请求一个层次也保留该维。用 `field_name` 指定变量名，
用 xarray 重命名坐标替代旧的 `level_dim`。

```{code-cell} ipython3
from reki.format.grib.eccodes import load_field_from_file, load_field_from_files
from reki.sources import get_source

file_path = get_source("test", "ecmwf_ifs").mutate().path
paths = [file_path]

first = load_field_from_files(paths, "t", "pl", None)
assert first.dims == ("time", "step", "latitude", "longitude")
assert first.pl.ndim == 0

layers = load_field_from_files(paths, "t", "pl", [850, 500], field_name="t")
old_axis = layers.rename({"pressure": "pl"})
old_axis = old_axis.assign_coords(pl=old_axis.pl.astype("float64"))
single_level = old_axis.sel(pl=850.0)
assert single_level.dims == first.dims
```

集合结果在返回前载入内存。按需读取单个文件时，先用单场入口的 `lazy=True`
选层和裁剪，再通过 `.values` 读取所选数据。
多文件零匹配返回 `None`，单文件 Dataset 零匹配返回空 Dataset。

```{code-cell} ipython3
from reki.format.grib import load_fields_from_file

field = load_field_from_file(file_path, "t", "pl", 850, lazy=True)
window = field.isel(latitude=slice(0, 2), longitude=slice(0, 2)).values
assert window.shape == (2, 2)
assert load_field_from_files(paths, "t", "pl", 700) is None
assert not load_fields_from_file(file_path, "t", "pl", 700).data_vars
```

`load_fields_from_file()` 使用 ecCodes，变量名源于原生 GRIB 键。
只读取一种变量、一个起报时间和一个时效时，可以恢复旧的变量名和维度。
如需旧版 cfgrib 的浮点精度，可显式转换为 `float32`。

```{code-cell} ipython3
dataset = load_fields_from_file(file_path, "t", "pl", [850, 500])
native_name, = dataset.data_vars
legacy_layout = dataset.isel(time=0, step=0).rename(
    {native_name: "t", "pressure": "isobaricInhPa"}
)
legacy_layout["t"] = legacy_layout["t"].astype("float32")
assert legacy_layout["t"].dims == ("isobaricInhPa", "latitude", "longitude")
```

(migration-grib-messages)=
## 原始 GRIB 消息

将 `count` 作为一基整数传入。此前使用 `True` 指定首条报文的调用可传
`count=1`，使用整数值浮点数的调用可在确认其为整数后转换。
浮点数和布尔值会触发 `QueryError`（`invalid_query`）。
`load_bytes_from_file()` 也接受 `count`，零匹配返回 `None`。
只需要原始字节时可以直接使用该入口。读取消息句柄时由调用方释放返回的句柄。

```{code-cell} ipython3
import eccodes
from reki.format.grib import load_message_from_file
from reki.format.grib.eccodes import load_bytes_from_file

configured_count = 2.0
assert configured_count.is_integer()
count = int(configured_count)
message = load_message_from_file(file_path, count=count)
assert message is not None
try:
    assert eccodes.codes_get_message(message) == load_bytes_from_file(file_path, count=count)
finally:
    eccodes.codes_release(message)
assert load_bytes_from_file(file_path, parameter="t", level_type="pl", level=700) is None
```

(migration-format-errors)=
## NetCDF 和 GrADS 异常

NetCDF 缺少变量或层值时，捕获 `QueryError` 并检查 `code == "no_match"`。
NetCDF 和 GrADS 缺少文件时，捕获 `SourceError` 并检查
`code == "resource_not_found"`。GrADS 惰性读取可能在 `.values` 才访问二进制
文件，应将取值操作放在同一个异常处理范围内。以下函数接收已有数据文件的路径。

```python
from cedarkit_query import QueryError, SourceError
from reki.format.grads import load_field_from_file as load_grads
from reki.format.netcdf import load_field_from_file as load_netcdf


def optional_netcdf(path, parameter, level):
    try:
        return load_netcdf(path, parameter=parameter, level=level)
    except QueryError as exc:
        if exc.code == "no_match":
            return None
        raise
    except SourceError as exc:
        if exc.code == "resource_not_found":
            return None
        raise


def optional_grads_values(path, forecast_time):
    try:
        field = load_grads(path, "t", level=500, forecast_time=forecast_time, lazy=True)
        return None if field is None else field.values
    except SourceError as exc:
        if exc.code == "resource_not_found":
            return None
        raise
```

(migration-grads-time)=
## GrADS 时效坐标

带起报时间和时效文件名的 CTL 会在字段上设置 `start_time`、`valid_time`
和 `forecast_time`。后者现在对应选中的记录。读取标记 +6h 的控制文件中的
0h 记录，会得到 0h 的坐标。需要 +6h 数据时显式筛选该记录。

```python
from reki.format.grads import load_field_from_file

field = load_field_from_file(
    "post.ctl_2020010100_006", "t", level=500, forecast_time="6h"
)
if field is not None:
    lead_time = field.coords["forecast_time"]
```

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
