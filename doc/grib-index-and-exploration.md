# GRIB 元数据索引与数据探索

ecCodes GRIB reader 可以持久化仅包含元数据的 SQLite 索引。索引用于加快字段
发现；它既不是 values 缓存，也不是下载缓存。本文所述的命令和元数据 API 都不会
解码 GRIB values。

## 字段发现

`all()` 返回不可变的 `FieldList`，其中包含按源文件顺序排列的惰性
`GribField` 引用。Python 位置从零开始；旧接口 `sel(count=N)` 仍使用从一开始的
GRIB message 序号，并忽略其他筛选条件。

```python
from reki import FieldQuery, from_source

reader = from_source("file", "forecast.grib2")
fields = reader.sel(FieldQuery(parameter="t", level_type="pl", level=[850, 500])).all()

assert len(fields) == 2
field = fields[0]             # 惰性字段引用
data = field.to_xarray()      # 此处才解码 values
```

空 `FieldList` 的 `first()` 返回 `None`。零个字段时 `one()` 抛出
`DataNotFoundError`，多个字段时抛出 `MultipleFieldsMatchedError`；
`one_or_none()` 只会在零个字段时返回 `None`。切片会返回另一个 `FieldList`；
`FieldList.concat()` 默认保留重复字段，除非传入 `deduplicate=True`。

以下仅元数据方法不会创建 xarray 对象或请求 `values`：`summary()`、
`metadata()`、`unique()`、`head()`、`describe()` 和 `ls()`。`metadata()` /
`ls()` 返回 DataFrame，`json()` 返回可安全编码为 JSON 的元数据记录。未知元数据键
会抛出 `KeyError`。`where()` 只接受 `FieldQuery` 或键值筛选，绝不执行 Python 或
SQL 表达式。

`fetch_many()` 为实验性 API。它保留输入顺序和重复位置；有索引时共享一次索引
会话，无索引批量查询最多执行一次 header 扫描。其 `cardinality` 可以是 `all`、
`first`、`one` 或 `one_or_none`。

## 索引策略与生命周期

默认策略为 `off`，因此常规读取会直接扫描，且绝不会创建索引。传入
`index_policy="auto"` 可显式启用：先读取有效索引；没有有效索引时尝试构建一次，
失败后回退为直接扫描。`readonly` 只读取有效索引；`refresh` 替换索引，失败时严格
报错。

索引根目录按以下优先级确定：显式 `index_dir`、`REKI_INDEX_DIR`、
`$XDG_CACHE_HOME/reki/indexes`（或 `~/.cache/reki/indexes`）。默认绝不使用源数据
目录。索引文件名是已解析绝对路径和 schema namespace 的哈希值，因此不会从文件名
泄漏路径。

v1 schema 为 `reki-grib-index/1`，只保存安全的 header 元数据和字节位置。有效性
检查包括已解析路径、device、inode、文件大小、纳秒 mtime、schema/query-rule/key-set
版本、支持的 GRIB edition 以及 ecCodes major 版本。对 `auto` 和 `readonly`，过期、
损坏、不支持、不可写或锁超时的索引会回退为直接扫描。`refresh` 会报告失败，并且
不会替换已有的有效索引。

构建器对每个索引使用 POSIX 建议锁，在最终索引目录写入唯一命名的临时 SQLite 文件，
验证后再原子替换发布。构建前后都会检查源文件指纹；文件变化时丢弃本次构建结果。
这些恢复路径绝不会修改源 GRIB 文件。

## CLI

```bash
reki inspect forecast.grib2 --json
reki ls forecast.grib2 --keys parameter,level_type,level,step --json
reki query forecast.grib2 --parameter t --level-type pl --level 850 --json
```

三个命令默认直接扫描。使用 `--use-index` 显式启用自动索引读取/构建；
`--read-only-index` 和 `--refresh-index` 也会显式启用对应索引模式。这些选项与
`--no-index` 互斥。`--index-dir` 指定索引目录，`--limit` 与 `--offset` 限制输出。
JSON 只写入 stdout，`--verbose` 将索引诊断输出到 stderr。无匹配是成功查询并返回
空结果；无效选项或键、以及严格 refresh 失败的退出码均为 2。

## Reader capability 矩阵

| reader | 元数据探索 | FieldList | 持久化索引 | fetch_many |
| --- | --- | --- | --- | --- |
| GRIB / ecCodes | 支持 | 支持 | 支持 | 实验性 |
| GRIB / cfgrib | 不支持 | 不支持 | 不支持 | 不支持 |
| NetCDF | 在支持时提供 summary / metadata | 不支持 | 不支持 | 不支持 |
| GrADS | 在支持时提供 summary / metadata | 不支持 | 不支持 | 不支持 |
| unknown | 不支持 | 不支持 | 不支持 | 不支持 |

调用方可在使用可选能力前检查冻结的 `reader.capabilities` 记录。不支持的操作会抛出
`UnsupportedOperationError`。
