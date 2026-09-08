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

# xarray 输出

`to_xarray()` 返回 `xarray.DataArray` 或格式适用时的 `Dataset`。用户可依赖的观察约定
包括空间坐标 `latitude` / `longitude`、可用的时间坐标（`time`、`step`、`valid_time`）、
层次坐标以及来源属性；具体字段、缺测值和维度仍由格式决定。

`to_numpy()` 适合只需要数值的场景；`to_pandas()` 适合表格或一维/二维数据。若 reader
不支持某项转换，会抛出 `UnsupportedOperationError`，而不会静默改变输出类型。处理操作
要求的坐标与维度见 {doc}`/guide/processing/new-api`；严格规范化与验证属于开发文档。

## 检查可观察的输出契约

下面的示例使用冻结 GRIB 数据。不要假设所有格式都有完全相同的维度名；先检查
`dims`、`coords` 和 `attrs`，再编写依赖时间或层次的计算：

```{code-cell} ipython3
from reki import from_source

field = from_source("test", "ecmwf_ifs").sel(
    parameter="2t", level_type="heightAboveGround", level=2,
).first()
assert field is not None
data = field.to_xarray()
{"dims": data.dims, "coordinates": sorted(data.coords)}
```

`xarray` 操作保留带标签的坐标。例如以下计算沿纬度求平均，而不是假定数组的某个位置轴
一定是纬度轴：

```{code-cell} ipython3
zonal_mean = data.mean("latitude")
zonal_mean.dims, zonal_mean.shape
```

## 多时效与集合坐标

`time` variant 为同一起报提供多个预报时效；`step` 和 `valid_time` 都是可观察坐标，
不应由数组位置推断：

```{code-cell} ipython3
time_data = from_source("test", "ecmwf_ifs", variant="time").sel(
    parameter="2t", level_type="heightAboveGround", level=2, step=[0, 6, 12, 24],
).to_xarray()
time_data.step.values.astype("timedelta64[h]").astype(int).tolist(), "valid_time" in time_data.coords
```

集合 variant 只包含真实扰动成员 1/2。固定一个 step 后，输出使用 `number` 成员维：

```{code-cell} ipython3
ensemble_data = from_source("test", "ecmwf_ifs", variant="ensemble").sel(
    parameter="2t", level_type="heightAboveGround", level=2, step=24,
).to_xarray()
ensemble_data.number.values.tolist()
```

若只需要原始数值，可显式使用 `to_numpy()`；这样会丢失坐标和属性，适合传给只接受数组
的库，而不适合作为后续空间处理的默认输入。
