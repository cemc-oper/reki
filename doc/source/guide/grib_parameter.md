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

# GRIB 要素检索

本页介绍 `sel()` 中 `parameter` 筛选条件的用法。
示例使用内置 `test` 数据源的 **ecmwf_ifs** 冻结数据集
（说明见 {doc}`/getting-started/test-data`），东亚资产包含地面要素
与等压面要素（500 hPa gh/t、850 hPa t/u/v），除标注外本页示例均可执行。

```{code-cell} ipython3
from reki import from_source

ds = from_source("test", "ecmwf_ifs")
```

## 背景：GRIB2 要素编码

GRIB2 要素由三个数字（GRIB 键）唯一确定：

| GRIB 键 | 描述 |
| --- | --- |
| `discipline` | 学科领域（码表 0.0） |
| `parameterCategory` | 要素类别（码表 4.1） |
| `parameterNumber` | 要素编号（码表 4.2） |

常见要素的编码：

| 要素 | discipline | parameterCategory | parameterNumber |
| --- | --- | --- | --- |
| 温度（temperature） | 0 | 0 | 0 |
| 位势高度（geopotential height） | 0 | 3 | 5 |
| 纬向风（u component of wind） | 0 | 2 | 2 |
| 经向风（v component of wind） | 0 | 2 | 3 |

更多要素编码可参考 ECMWF 的
[Parameter Database](https://codes.ecmwf.int/grib/param-db/)。

GRIB 是表格驱动的数据格式：文件中保存的是数字编码，要素名称是
外部表格对编码的映射。reki 的 `parameter` 参数支持三类名称——
ecCodes `shortName`、WGRIB2 要素名、CEMC 要素名——也支持直接用
数字编码（字典形式）。字符串名称的解析顺序是：先查 reki 内置的
要素注册表（WGRIB2 名 → CEMC 要素名），注册表中没有的名称再按
ecCodes `shortName` 匹配。

## ecCodes shortName

ecCodes 内置的 `shortName` 是最通用的要素名写法，
ecmwf_ifs 数据集中的要素都可以用 `shortName` 检索：

```{code-cell} ipython3
t2m = ds.sel(parameter="2t", level_type="heightAboveGround", level=2).to_xarray()
t2m.shape
```

```{code-cell} ipython3
gh500 = ds.sel(parameter="gh", level_type="pl", level=500).to_xarray()
float(gh500.mean())
```

```{code-cell} ipython3
tp = ds.sel(parameter="tp", level_type="sfc", level=0).to_xarray()
tp.shape
```

:::{note}
`shortName` 由 ecCodes 的表格定义，与 ecCodes 版本有关，不同版本
可能不同，升级 ecCodes 后请留意。ecCodes 无法识别的本地编码要素
（`shortName` 显示为 `unknown`）不能用名称检索，可改用下文的
字典形式直接指定数字编码。
:::

## WGRIB2 要素名

reki 内置了 WGRIB2 使用的要素表格（要素注册表的 `wgrib2_name`
列），支持 WGRIB2 要素名。下面的写法与 `"2t"` 完全等价：

```{code-cell} ipython3
t2m_wgrib2 = ds.sel(
    parameter="TMP",
    level_type="heightAboveGround",
    level=2,
).to_xarray()
bool((t2m_wgrib2 == t2m).all())
```

位势高度和风的 WGRIB2 名：

```{code-cell} ipython3
gh500_wgrib2 = ds.sel(parameter="HGT", level_type="pl", level=500).to_xarray()
float(gh500_wgrib2.mean())
```

```{code-cell} ipython3
u850_wgrib2 = ds.sel(parameter="UGRD", level_type="pl", level=850).to_xarray()
float(u850_wgrib2.mean())
```

## CEMC 要素清单

reki 内置了 CEMC 的要素注册表（`param_registry.yaml`），
支持 CEMC 自定义的变量名。注册表可以通过
`get_param_registry()` 查询：

```{code-cell} ipython3
import pandas as pd

from reki.readers.grib.config import get_param_registry

registry = get_param_registry()
rows = []
for (discipline, category, number), entry in registry.items():
    rows.append({
        "name": entry["name"],
        "discipline": discipline,
        "category": category,
        "number": number,
        "wgrib2_name": entry.get("wgrib2_name"),
    })
param_table = pd.DataFrame(rows)
param_table.head(n=10)
```

CEMC 要素名可以附带层次信息。例如 `"t2m"` 在注册表中绑定了
`heightAboveGround`/2 米的层次条件，检索时无需再指定
`level_type`/`level`，结果与 `"2t"` 完全一致：

```{code-cell} ipython3
t2m_cemc = ds.sel(parameter="t2m").to_xarray()
bool((t2m_cemc == t2m).all())
```

:::{note}
注册表中还定义了一批 CMA 模式特有的要素名（如辐射亮温 `"bti"`、
0–3 km 垂直风切变 `"shr(0-3000)"`），需要 CMA 模式 GRIB2 数据
（CMA-HPC / CMADaaS 环境），以下示例不参与执行：

```python
field = ds.sel(parameter="bti").to_xarray()
field = ds.sel(parameter="shr(0-3000)").to_xarray()
```
:::

## 字典形式（GRIB 键）

`parameter` 也可以直接给字典形式的 GRIB 键条件，
适合所有名称表格都覆盖不到的要素。下面的写法与
`parameter="t"` 完全等价：

```{code-cell} ipython3
t500_dict = ds.sel(
    parameter={
        "discipline": 0,
        "parameterCategory": 0,
        "parameterNumber": 0,
    },
    level_type="pl",
    level=500,
).to_xarray()
t500_str = ds.sel(parameter="t", level_type="pl", level=500).to_xarray()
bool((t500_dict == t500_str).all())
```

:::{note}
理论上 `parameter` 的字典中可以设置任意 GRIB 键，但建议把层次、
时效等条件分散到对应的筛选参数中（`level_type`/`level`/`count`）。
`sel()` 还支持把任意 GRIB 键作为关键字参数传入，
见 {doc}`/guide/data_load`。
:::

:::{note}
**ecmwf_ifs 数据集包含修改后的 ECMWF IFS 开放数据**，© ECMWF，
按 CC-BY-4.0 许可使用。完整署名见 {doc}`/getting-started/test-data`。
:::
