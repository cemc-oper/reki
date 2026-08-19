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

# 数据处理

`reki.operator` 提供常用的格点数据操作：区域裁剪、站点提取、网格插值
与降采样。本页示例使用 `test` 数据源 **ecmwf_ifs** 数据集的全球区域
（`domain="global"`，2 米温度全球场，说明见
{doc}`/getting-started/test-data`）。

```{code-cell} ipython3
import numpy as np
import xarray as xr

from reki import from_source

ds = from_source("test", "ecmwf_ifs", domain="global")
t2m = ds.sel(parameter="2t", level_type="heightAboveGround", level=2).to_xarray()
t2m
```

## 裁剪区域

`extract_region()` 从格点场中裁出经纬度范围
（`start_latitude` / `end_latitude` 按南→北给出，与坐标排列方向无关）：

```{code-cell} ipython3
from reki.operator import extract_region

region = extract_region(
    t2m,
    start_longitude=60,
    end_longitude=150,
    start_latitude=0,
    end_latitude=60,
)
region.shape
```

裁剪东亚区域后的纬向平均：

```{code-cell} ipython3
float(region.mean())
```

## 提取站点

`extract_point()` 提取任意经纬度点上的值，支持线性插值（默认）
与最近邻（`scheme="nearest"`），也可一次提取多个点：

```{code-cell} ipython3
from reki.operator import extract_point

# 北京附近，最近邻
extract_point(t2m, latitude=39.9, longitude=116.4, scheme="nearest").values
```

```{code-cell} ipython3
# 北京、上海，双线性插值
extract_point(
    t2m,
    latitude=[39.9, 31.2],
    longitude=[116.4, 121.5],
).values
```

## 网格插值

`interpolate_grid()` 把要素场插值到目标网格。目标网格用一个带有
`latitude` / `longitude` 坐标的 `xarray.DataArray` 描述（取值无关），
下面用 numpy 合成一个 0.5° 的东亚区域网格：

```{code-cell} ipython3
lats = np.arange(60, -0.01, -0.5)
lons = np.arange(60, 150.01, 0.5)
target_grid = xr.DataArray(
    np.zeros((len(lats), len(lons))),
    coords=[("latitude", lats), ("longitude", lons)],
)

from reki.operator import interpolate_grid

t2m_fine = interpolate_grid(t2m, target_grid, scheme="linear")
t2m_fine.shape
```

可选 `scheme` 包括 `"linear"`（默认）、`"nearest"` 等；
`engine="scipy"` 时使用 scipy 插值后端。

```{code-cell} ipython3
float(t2m_fine.mean())
```

## 降采样

`sample_nearest()` 按目标分辨率对网格做最近邻（跨步）抽样，
结果是原网格的子集，不引入插值误差：

```{code-cell} ipython3
from reki.operator import sample_nearest

coarse = sample_nearest(t2m, longitude_step=2.5, latitude_step=2.5)
coarse.shape
```

:::{note}
**ecmwf_ifs 数据集包含修改后的 ECMWF IFS 开放数据**，© ECMWF，
按 CC-BY-4.0 许可使用。完整署名见 {doc}`/getting-started/test-data`。
:::
