# GrADS

GrADS reader 需要 `.ctl` 控制文件及其引用的数据文件。通过 `from_source("file", path)`
交给 dispatch 识别后，可使用 `sel()` 和 `to_xarray()`；数组会按控制文件中的时间、层次
和网格定义构造。缺少关联数据文件、非标准控制文件或不支持的选择条件会以读取错误或
`UnsupportedOperationError` 失败。

这是本地文件能力；示例应提供自己的固定 `.ctl` 资产，不应假定业务目录存在。
