---
jupytext:
  text_representation:
    extension: .md
    format_name: myst
    format_version: 0.13
    jupytext_version: 1.16.0
kernelspec:
  display_name: Python 3
  language: python
  name: python3
---

# 使用推荐 API 处理数据

`extract_region()` 裁剪经纬度区域，`sample_nearest()` 按目标步长保留最近的原网格点，
`extract_point()` 可按指定方式提取站点，`interpolate_grid()` 将场插值到目标网格。
它们接收 `xarray.DataArray`，要求可识别的 `latitude` 和 `longitude` 坐标。

## 区域裁剪与规则抽稀

```{code-cell} ipython3
from reki import from_source
from reki.operator import extract_region, sample_nearest

field = from_source("test", "ecmwf_ifs").sel(
    parameter="2t", level_type="heightAboveGround", level=2,
).first()
assert field is not None
data = field.to_xarray()

subset = extract_region(data, 105, 125, 25, 45)
coarse = sample_nearest(subset, longitude_step=2, latitude_step=2)
subset.shape, coarse.shape
```

`sample_nearest()` 不是站点采样：它不创建新值，而是以输入网格第一个点为锚点按步长抽取。
站点或任意经纬度位置应使用 `extract_point()`：

```{code-cell} ipython3
from reki.operator import extract_point

beijing = extract_point(data, latitude=39.9, longitude=116.4, scheme="nearest")
beijing.values
```

## 明确错误边界

缺少 `latitude` / `longitude` 坐标或把普通 ndarray 传入时，操作会失败。及早检查输入能让
错误靠近数据接入处；区域外站点和插值边界的行为则取决于显式选择的 xarray/SciPy 方法：

```python
if not {"latitude", "longitude"}.issubset(data.coords):
    raise ValueError("处理前需要带 latitude 和 longitude 坐标的 DataArray")
```

区域裁剪会处理升序或降序纬度坐标；目标范围之外的站点、缺少坐标和不兼容维度会失败，
而不是推断坐标。最近邻采样、插值和步长抽取不是同一语义：最近邻不生成新值，插值依赖
xarray 或 SciPy 引擎，步长只选择已有格点。

`interpolate_grid()` 的目标应是带经纬度坐标的 `DataArray`。缺测值、边界外目标和返回
维度遵循底层 xarray/SciPy 插值能力；需要稳定行为时应显式选择方法并在业务数据上验证。
通用输出坐标约定见 {doc}`/guide/loading/xarray-output`。
