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

# data_finder 配置文件

:::{important}
本页属于**旧 API（兼容层）**文档，但配置文件机制**新旧 API 共用**：
`reki.data_finder` 的查找函数与新 API 的 `local` 数据源
（见 {ref}`data_find_local`）使用同一套配置文件，自定义配置目录时
（`config_dir` 参数）本页内容对两者均适用。
:::

data_finder 使用配置文件描述"文件名 + 候选目录列表"：查找时按顺序
在各个候选目录中检查文件是否存在，找到即返回完整路径。reki 内置了
CEMC 各业务系统的配置文件，位于 `reki/data_finder/conf/` 目录。

## 配置文件的定位

配置文件路径由三部分拼接而成：

```text
{config_dir}/{data_class}/{data_type}.yaml
```

- `config_dir`：配置根目录，默认为 reki 内置的
  `reki/data_finder/conf/`，可用 `config_dir` 参数覆盖
- `data_class`：数据类别子目录，内置配置分为 `od`（CMA-HPC 业务
  存储）、`cmadaas`（CMADAAS 挂载盘）、`cm` 等
- `data_type`：数据类型，即配置文件的相对路径（不含 `.yaml` 后缀），
  如 `"cma_gfs_gmf/grib2/orig"`

## 配置文件格式

配置文件是 YAML 格式，同时也是一个 **Jinja2 模板**：查找时先用
起报时次、预报时效等变量渲染模板，再按 YAML 解析。下面是一个典型
的配置文件（`od/cma_gfs_gmf/grib2/orig.yaml`，有删减）：

```yaml+jinja
{% set start_time_string = time_vars.year ~ time_vars.month ~ time_vars.day ~ time_vars.hour %}

file_name: 'gmf.gra.{{ start_time_string }}{{ time_vars.forecast_hour }}.grb2'

paths:
  # HPC2023
  - type: local
    level: archive
    path: '/g3/COMMONDATA/OPER/CEMC/GFS_GMF/Prod-grib/{{ start_time_string }}/ORIG'

  # CMA Storage
  - type: local
    level: storage
    path: '/sstorage/COMMONDATA/OPER/CEMC/GFS_GMF/Prod-grib/{{ start_time_string }}/ORIG'

  # CEMC Storage
  - type: local
    level: storage
    path: '{{ query_vars.storage_base }}/GRAPES_GFS_GMF/Prod-grib/{{ start_time_string }}/ORIG'
```

配置文件主要包含两部分：

- **文件名**：`file_name` 为单个文件名；`file_names` 为文件名列表
  （`get_local_file_name()` 取第一个）
- **文件目录**：`paths` 为候选目录列表，每个条目包含三个字段：
  - `type`：目录类型（`local` 等，保留字段）
  - `level`：存储级别（`archive` / `storage` / `runtime` 等），
    供 `data_level` 参数过滤
  - `path`：目录路径模板

查找时按 `paths` 列表顺序逐个尝试，跳过不在 `data_level` 范围内的
条目，找到第一个存在的文件即返回。

## 内置模板变量

模板中可以使用两个内置变量对象。

### TimeVars

`time_vars` 包含起报时间和预报时效信息：

| 属性 | 描述 | 示例 |
| --- | --- | --- |
| `start_time` | 起报时间（`pd.Timestamp`） | `2026-08-18 00:00:00` |
| `forecast_time` | 预报时效（`pd.Timedelta`） | `1 days 00:00:00` |
| `year` | 起报年，4 位字符串 | `2026` |
| `month` | 起报月，2 位字符串 | `08` |
| `day` | 起报日，2 位字符串 | `18` |
| `hour` | 起报时，2 位字符串 | `00` |
| `minute` | 起报分，2 位字符串 | `00` |
| `forecast_hour` | 预报时效小时，3 位字符串 | `024` |
| `forecast_minute` | 预报时效分钟，2 位字符串 | `00` |

```{code-cell} ipython3
import pandas as pd
from pprint import pprint

from reki.data_finder._util import TimeVars

time_vars = TimeVars(
    start_time=pd.Timestamp("2026-08-18 00:00"),
    forecast_time=pd.to_timedelta("24h"),
)
pprint(time_vars.__dict__)
```

### QueryVars

`query_vars` 包含检索需要的其他变量，来自调用查找函数时传入的
关键字参数。常用变量：

- `storage_base`：存储根目录（如 `/CMADAAS`），默认为 `None`
- `obs_time`：观测资料时间，传入 `obs_time` 参数时自动包装为
  `TimeVars` 对象
- 任意自定义变量：如集合预报配置中的 `number`，传入的关键字参数
  都会成为 `query_vars` 的属性

## 内置模板函数

模板中还注册了一批函数，用于在模板内进行简单的时间计算。

针对起报时间：

- `generate_start_time(start_time, hour)`：起报时间偏移 `hour`
  小时，生成新的起报时间
- `get_year(start_time)` / `get_month(start_time)` /
  `get_day(start_time)` / `get_hour(start_time)` /
  `get_minute(start_time)`：返回对应的时间字符串

针对预报时效：

- `generate_forecast_time(forecast_time, time_interval)`：预报时效
  偏移一个时间段（如 `"3h"`）
- `get_forecast_hour(forecast_time)` / `get_forecast_minute(forecast_time)`：
  返回对应的时效字符串

例如观测准备文件 `rec_R2CWE` 的文件名中使用起报时次前 3 小时的
时间，配置（`od/cma_gfs_gmf/obs/r2cwe.yaml`）用
`generate_start_time()` 计算新的起报时间：

```yaml+jinja
{% set start_time_string = time_vars.year ~ time_vars.month ~ time_vars.day ~ time_vars.hour %}
{% set start_time_4dv = generate_start_time(time_vars.start_time, -3) %}
{% set start_time_4dv_string = get_year(start_time_4dv) ~ get_month(start_time_4dv) ~ get_day(start_time_4dv) ~ get_hour(start_time_4dv) %}

file_name: 'rec_R2CWE_{{ start_time_4dv_string }}{{ query_vars.obs_time.hour }}{{ query_vars.obs_time.minute }}_g.dat'

paths:
  - type: local
    level: archive
    path: '/g3/COMMONDATA/OPER/CEMC/GFS_GMF/Obs-prep/{{ start_time_string }}'
```
