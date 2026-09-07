# 兼容 API：data_finder

`reki.data_finder.find_local_file()`、`find_local_files()` 和
`get_local_file_name()` 保持兼容，适合维护已有的业务路径模板；新代码优先使用
`from_source("local", ...)`，并在需要读取时继续调用 `sel()`/`to_xarray()`。

旧入口和新 `local` source 共用 YAML/Jinja2 配置，但资源所有权不同：旧函数返回
`pathlib.Path` 或路径集合，不会打开数据；新入口返回统一读取对象。完整参数、模板变量、
调试方式及迁移前的示例保留在 {doc}`/guide/legacy_find` 和
{doc}`/guide/legacy_finder_config`。
