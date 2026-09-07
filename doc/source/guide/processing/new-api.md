# 使用推荐 API 处理数据

`extract_region()` 裁剪经纬度区域，`sample_nearest()` 选择最近格点，
`extract_point()` 可按指定方式提取站点，`interpolate_grid()` 将场插值到目标网格。
它们接收 `xarray.DataArray`，要求可识别的 `latitude` 和 `longitude` 坐标。

```python
from reki.operator import extract_region, sample_nearest

subset = extract_region(data, 105, 125, 25, 45)
stations = sample_nearest(data, longitude=[116.4], latitude=[39.9])
```

区域裁剪会处理升序或降序纬度坐标；目标范围之外的站点、缺少坐标和不兼容维度会失败，
而不是推断坐标。最近邻采样、插值和步长抽取不是同一语义：最近邻不生成新值，插值依赖
xarray 或 SciPy 引擎，步长只选择已有格点。

`interpolate_grid()` 的目标应是带经纬度坐标的 `DataArray`。缺测值、边界外目标和返回
维度遵循底层 xarray/SciPy 插值能力；需要稳定行为时应显式选择方法并在业务数据上验证。
通用输出坐标约定见 {doc}`/guide/loading/xarray-output`。
