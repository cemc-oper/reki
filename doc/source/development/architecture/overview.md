# 架构概览

reki 将“在哪里找数据”和“怎样读取数据”分离：source 负责定位，reader 负责格式识别，
core 模型保存查询与 metadata，operator 只处理规范化数组。

```text
SourceSpec / from_source → Source mutate → reader dispatch → FieldList / Field
                                                        → xarray → operator
```

扩展 source 或 reader 前先阅读 {doc}`source-reader-pipeline`；处理层不能反向依赖
GRIB 私有实现。常见失败是把远程 I/O 放在 source 构造函数中，导致惰性边界失效。
相应公开类型见 {doc}`../api/sources`、{doc}`../api/readers` 和 {doc}`../api/core`。
