# Source 与 reader 调度

`from_source()` 依次查询程序注册、`reki.sources` entry point 和内置模块；创建 source
后运行 `mutate()` 直至对象不再变化，再调用 `to_data_object()`。文件 source 最终交由
reader 的快速/深度两阶段探测处理。

```text
name → register / entry point / builtin → Source → mutate fixed point
     → FileSource → explicit reader | magic probe → Reader | UnknownReader
```

远程 source 标记 `remote=True` 时返回 `LazySource`，首次属性访问才执行 pipeline。
扩展点是 source class、entry point 和 reader 的 `READER` factory；不要在探测阶段解码
值或发起远程请求。未知文件必须返回 `UnknownReader`，而不是误认格式。API：
{doc}`../api/sources`、{doc}`../api/readers`。
