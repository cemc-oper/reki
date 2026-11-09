# GrADS

受保护读取函数保留 CTL / 二进制格式的选择和 DataArray 行为，不强加 GRIB 业务组织。

```python
from reki.readers.grads import load_field_from_file

field = load_field_from_file("post.ctl_2026110212_006", parameter="gh", level_type="pl", level=850, lazy=True)
```

缺参数、层次或时间的正常查询返回 None。起报时间可从支持的业务 CTL 文件名推导，
每条记录的 forecast_time 为其 valid_time 减起报时间；通用 CTL 使用其相对时间定义。
小端、字节序与 sequential 记录由 CTL 选项控制；原文件必须在惰性访问时仍可读。
缺资源和损坏数据分别为 SourceError(resource_not_found / decode_failed)，不会作为缺场。
