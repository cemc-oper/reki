# GRIB2 工作流

本专题使用冻结的 `ecmwf_ifs` 数据，按真实工作顺序组织：先只读 header 探索，再精确
选择字段，最后转换为 xarray 或进入处理步骤。所有 E1/E2 程序均使用 `make -C doc data`
准备的固定资产；不要把业务目录或当前日期作为输入。

```{toctree}
:maxdepth: 1

open-and-inspect
select-fields
parameters
levels
time-and-step
ensemble
metadata-and-native-keys
multiple-fields
lazy-loading
indexes
xarray-output
engines
cli
troubleshooting
```

从 {doc}`open-and-inspect` 开始；已知任务可直接进入相应页面。旧
{doc}`/guide/loading/grib` 页面保留为兼容入口。
