# GRIB 扫描与索引边界

公开来源与受保护函数仅使用 ecCodes 头扫描与按需值解码，不再访问持久索引。

```text
GRIB file → header scan → select native records → decode → native array / public Dataset
```

高频旧函数保存路径和所选报文偏移，lazy=True 在值访问时才解码。低频集合在来源关闭前
生成独立内存结果。with_index True / 字符串只发一次 FutureWarning，路径零访问；旧 CLI
显式索引策略报 unsupported。内部历史 IndexStore 不是公开 API 或正在使用的缓存层。
读取与格式行为见 {doc}`/guide/legacy_grib`。
