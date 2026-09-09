# 查找数据时的排错顺序

1. 对 `file` 和 `file-pattern`，先确认渲染后的路径存在；路径错误不是字段零匹配。
2. 对 `local`，确认 catalog 名称、起报时间、时效、成员和 storage 层级，再查看配置渲染。
3. 对 `url` 和 `cmadaas`，在首次 I/O 调用处记录安全的异常类型和状态，不记录凭据。
4. 路径已打开但查询为空时，改用 `unique()`、`ls()` 或 {doc}`/guide/grib/open-and-inspect`
   核对参数、层次和时效。

冻结 `test` source 只用于示例和测试，不是业务数据通道。它能帮助区分“source/环境问题”
与“GRIB 字段选择问题”。
