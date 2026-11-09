# 时间、时效与时间范围

公共 `time` 为 UTC 起报时间，`step` 为显式时长，例如 `PT6H`；valid_time 由二者组成。
统计场另有区间与统计类型，不能把末端时效当作累计长度。身份和原始 GRIB 时钟在
Field.identity / metadata 中分别保留，未知单位或时钟歧义不能靠文件名猜测。

```python
selected = source.sel(native={"grib": {"shortName": "t"}}, time="2026-11-02T12:00:00Z", step="PT6H")
field = selected.one()
identity = field.identity.to_dict()
```

受保护 GRIB 函数的旧 `start_time/forecast_time/valid_time` 是头过滤条件，支持已有
时间对象与明确时长；起报字符串可用 YYYYmmddHH。它们不增加第二套公共 Query schema。
实际降水窗口必须有独立端点和生产定义，见 {doc}`/guide/public-query`。
