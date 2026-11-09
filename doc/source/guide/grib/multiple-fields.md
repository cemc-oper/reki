# 多字段查询

公共 Request 的 queries 保存多条独立 Query；QuerySource.sel 也可接收多个查询。
结果保留来源范围、实际记录及完整 report，不使用旧 reader.fetch_many 作为公共 SDK。

```python
from reki import Query

queries = [Query(native={"grib": {"shortName": "t"}}, level_type="pressure", level=level) for level in [850, 500]]
```

实际执行形式及 Request 文件见 {doc}`/guide/public-query`；多结果转 Dataset 时先按变量
分组，再核输出位置与网格。重复查询不代表可以丢失来源证据。受保护的多文件 DataArray
适配只允许单变量，零匹配 None；单文件 Dataset 适配可返回携带 report 的空 Dataset。
