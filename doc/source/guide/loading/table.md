# 表格与未知格式

表格 reader 将受支持的文本表转换为 `pandas.DataFrame`，首选 `to_pandas()`；
`to_xarray()` 是 DataFrame 的直接转换，不提供 GRIB 字段选择语义。NWPC 的
RGWST、RSURF、R2CWE、RSING 和 RTEMP 观测表格继续使用
`reki.readers.table.load_nwpc_obs_from_file()` 或兼容的 `reki.format.table` 入口。
分隔符、列名和特定观测格式由输入文件及 reader 选项决定。

无法识别的文件返回 `UnknownReader`，保留原始路径/字节而不假装已解析。应显式指定
reader 或先检查文件格式，而不是将未知格式当作空数据集。
