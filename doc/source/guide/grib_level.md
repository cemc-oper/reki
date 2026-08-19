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

# GRIB 层次检索

本页介绍 `sel()` 中 `level_type` / `level` 两个筛选条件的用法。
示例使用内置 `test` 数据源的 **ecmwf_ifs** 冻结数据集
（说明见 {doc}`/getting-started/test-data`），东亚资产包含地面要素
与等压面要素（500 hPa gh/t、850 hPa t/u/v），本页示例均可执行。

```{code-cell} ipython3
from reki import from_source

ds = from_source("test", "ecmwf_ifs")
```

## 背景：产品模板与层次键

GRIB2 要素场的层次信息由产品模板
（`productDefinitionTemplateNumber`）定义。常见模板 4.0（瞬时要素）
和 4.8（统计要素）都支持**两个**固定面（fixed surface）层次，
每个层次由层次类型和层次值组成，相关 GRIB 键如下：

| GRIB 键 | 描述 |
| --- | --- |
| `typeOfFirstFixedSurface` | 第一层次类型（码表 4.5） |
| `scaleFactorOfFirstFixedSurface` | 第一层次值的比例因子 |
| `scaledValueOfFirstFixedSurface` | 第一层次值的缩放值 |
| `typeOfSecondFixedSurface` | 第二层次类型 |
| `scaleFactorOfSecondFixedSurface` | 第二层次值的比例因子 |
| `scaledValueOfSecondFixedSurface` | 第二层次值的缩放值 |

层次值的计算公式：

$$
level = 10^{-f} \cdot v
$$

其中 `f` 是 `scaleFactorOfFirstFixedSurface`，`v` 是
`scaledValueOfFirstFixedSurface`（第二层次同理）。
单层次要素的第二层次类型为 255（缺失）。

ecCodes 额外提供 `typeOfLevel` 和 `level` 两个抽象键，把第一层次的
类型（字符串，如 `"isobaricInhPa"`）和数值（已按单位换算，如 hPa）
暴露出来，覆盖大部分常见单层次要素场。reki 的 `level_type` /
`level` 筛选条件即建立在这两个键之上。

ecmwf_ifs 东亚资产包含的层次：

| 要素 | `typeOfLevel` | `level` |
| --- | --- | --- |
| `tp` | `surface` | 0 |
| `10u` / `10v` | `heightAboveGround` | 10 |
| `2t` / `2d` | `heightAboveGround` | 2 |
| `msl` | `meanSea` | 0 |
| `gh` / `t` | `isobaricInhPa` | 500 |
| `t` / `u` / `v` | `isobaricInhPa` | 850 |

## typeOfLevel 字符串

最直接的写法：`level_type` 给 ecCodes `typeOfLevel` 字符串，
`level` 给对应的层次值：

```{code-cell} ipython3
t2m = ds.sel(parameter="2t", level_type="heightAboveGround", level=2).to_xarray()
t2m.shape
```

```{code-cell} ipython3
msl = ds.sel(parameter="msl", level_type="meanSea", level=0).to_xarray()
float(msl.mean())
```

等压面层次使用 `"isobaricInhPa"`，层次值单位为 hPa：

```{code-cell} ipython3
t500 = ds.sel(parameter="t", level_type="isobaricInhPa", level=500).to_xarray()
float(t500.mean())
```

## reki 内置层次别名

reki 内置几种层次别名，用于简化常用查询：

| 别名 | 描述 | 等价的 GRIB 键条件 |
| --- | --- | --- |
| `pl` | 等压面层，单位 hPa | `typeOfFirstFixedSurface:int=100` |
| `sfc` | 地面层 | `typeOfLevel=surface` |
| `ml` | 模式面层 | `typeOfFirstFixedSurface:int=131` |

`sfc` 匹配 `typeOfLevel="surface"` 的要素（注意：2 米温度等
`heightAboveGround` 要素**不属于** `sfc`）：

```{code-cell} ipython3
tp = ds.sel(parameter="tp", level_type="sfc", level=0).to_xarray()
tp.shape
```

`pl` 用于等压面层，单位 hPa，支持浮点层次值：

```{code-cell} ipython3
gh500 = ds.sel(parameter="gh", level_type="pl", level=500).to_xarray()
float(gh500.mean())
```

:::{note}
`ml`（模式面层）是 CMA 模式（如 CMA-GFS 的 modelvar 产品）特有的
层次类型，ecmwf_ifs 数据集中没有模式面要素，以下示例不参与执行：

```python
field = ds.sel(parameter="t", level_type="ml", level=20).to_xarray()
```
:::

## 字典形式的 level_type（GRIB 键）

`level_type` 也接受字典，直接使用 GRIB 键作为筛选条件，
适合 ecCodes `typeOfLevel` 抽象键覆盖不了的层次类型：

```{code-cell} ipython3
t2m_dict = ds.sel(
    parameter="2t",
    level_type={"typeOfFirstFixedSurface:int": 103},
    level=2,
).to_xarray()
t2m_dict.shape
```

:::{note}
键名中的 `:int` 后缀显式指定按键的整数形式比较（103 是码表 4.5 中
`heightAboveGround` 的编码值）。如果不标注类型，按键的**字符串**
形式比较——而 ecCodes 对常见编码值的字符串形式是别名（如 `"sfc"`、
`"pl"`）而非数字字符串，因此使用数值编码时请始终带上 `:int`。
:::

字典形式与别名等价。下面的两种写法结果完全一致：

```{code-cell} ipython3
t500_alias = ds.sel(parameter="t", level_type="pl", level=500).to_xarray()
t500_dict = ds.sel(
    parameter="t",
    level_type={"typeOfLevel": "isobaricInhPa"},
    level=500,
).to_xarray()
bool((t500_alias == t500_dict).all())
```

## 多层次检索

`level` 传入列表可一次检索多个层次，多层次的同名要素会合并为
带层次维的 `xarray.Dataset`：

```{code-cell} ipython3
t_multi = ds.sel(parameter="t", level_type="pl", level=[850, 500]).to_xarray()
t_multi
```

## 双层次要素：first_level / second_level

使用两个固定面定义层次的要素场（如土壤层、厚度层、气压层间的
统计量，常见于产品模板 4.8），ecCodes 的 `level` 抽象键无法完整
表达。reki 提供 `first_level` / `second_level` 两个内置键，
按层次值公式计算后比较，可放入 `level` 的字典形式中：

```python
# CMA-GFS 0.1–0.4 m 土壤温度层（typeOfLevel=depthBelowLandLayer）
field = ds.sel(
    parameter="t",
    level_type="depthBelowLandLayer",
    level={"first_level": 0.1, "second_level": 0.4},
).to_xarray()
```

:::{note}
上述双层次示例需要 CMA 模式 GRIB2 数据（CMA-HPC / CMADaaS 环境），
不参与执行。ecmwf_ifs 数据集只包含单层次要素。
:::

对单层次要素，`level` 的字典形式同样可用（此时只有
`first_level` 有意义）：

```{code-cell} ipython3
t2m_first = ds.sel(
    parameter="2t",
    level_type="heightAboveGround",
    level={"first_level": 2},
).to_xarray()
t2m_first.shape
```

:::{note}
**ecmwf_ifs 数据集包含修改后的 ECMWF IFS 开放数据**，© ECMWF，
按 CC-BY-4.0 许可使用。完整署名见 {doc}`/getting-started/test-data`。
:::
