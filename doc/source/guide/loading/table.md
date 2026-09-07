# 表格与未知格式

表格 reader 将受支持的文本表转换为 `pandas.DataFrame`，因此使用 `to_pandas()`；它不承诺
`to_xarray()`。分隔符、列名和特定观测格式由输入文件及 reader 选项决定。

无法识别的文件返回 `UnknownReader`，保留原始路径/字节而不假装已解析。应显式指定
reader 或先检查文件格式，而不是将未知格式当作空数据集。
