# 扩展 reader

reader factory 接收 source、path、magic 和 `deeper_check`，快速探测不能读取大量内容；深度
探测才可检查格式结构。返回 `None` 表示不认领，返回 Reader 表示认领。

```text
magic probe → None | Reader → deep probe → Reader → metadata / conversion methods
```

实现 capabilities、`sel()`、metadata 及受支持的转换；不支持的操作抛出
`UnsupportedOperationError`。明确 reader 名称应绕过自动分派。API：
{doc}`../api/readers`，GRIB 参考见 {doc}`../architecture/grib-reader-and-index`。
