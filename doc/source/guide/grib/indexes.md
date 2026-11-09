# 索引退出

公共 v1 查询不读写持久索引。受保护旧读取函数保留 with_index 调用形式：省略或 False
无提示，True / 原有合法路径字符串发出一次定位到外部调用方的 FutureWarning 后继续读取。
被忽略的索引路径不会被 stat、读取、创建、更新或删除，也不检查存在性或可写性。

```python
from reki.format.grib import load_field_from_file

field = load_field_from_file("original.grib2", parameter="t", with_index=False)
```

旧资料探索 CLI 的启用 / 只读 / refresh 选项报 unsupported；普通扫描继续工作。
内部历史 IndexStore 模块不作为公开缓存协议，不能据其仍在源码中推断读取入口使用索引。
