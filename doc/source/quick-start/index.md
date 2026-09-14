# 快速开始

本章节面向首次使用 reki 的用户，用一组固定的 ECMWF IFS GRIB2 测试数据完成“查找 → 加载 → 处理”的最小闭环。
整个示例预计需要 10～15 分钟，不访问 CMA 内网、业务滚动数据或个人配置。

## 完成本章节后

你将能够：

- 安装 reki 及其 GRIB2 支持；
- 下载并使用可重复的 `ecmwf_ifs` 测试数据；
- 创建 `source` 并探索 GRIB header 元数据；
- 按参数、层次等条件选择字段；
- 将字段转换为 `xarray.DataArray`；
- 对结果执行一次区域裁剪。

最终工作流会得到一个 2 米温度场，维度为 `latitude × longitude`，然后从中裁剪出东亚的一部分区域。

## 开始前

请准备：

- Python 3.11 或更高版本；
- 一个可以安装 Python 包的环境，推荐使用 `uv`；
- 首次下载测试数据所需的网络连接；
- 用于保存测试数据缓存的本地磁盘空间。

测试数据来自公开的固定 ECMWF IFS 数据集。它适合文档示例、自动化测试和问题复现；
不要用滚动的 `cma_gfs` 数据替代本章节中的固定数据。

## 推荐路线

按下面的顺序阅读：

1. {doc}`installation`：安装 reki，并了解 `cmadaas`、`lazy` 等可选依赖；
2. {doc}`test-data`：下载默认的东亚测试数据，必要时再下载全球场或其他 variant；
3. {doc}`first-workflow`：运行完整示例，完成数据探索、字段选择、xarray 转换和区域裁剪。

如果只想先验证安装是否成功，可以先执行：

```bash
uv add reki
uv run reki-test-data download ecmwf_ifs
```

下载完成后，继续运行 {doc}`first-workflow`。示例会使用内置的 `test` source：

```python
from reki import from_source

source = from_source("test", "ecmwf_ifs")
```

## 按目标继续阅读

完成第一个工作流后，可以根据任务进入相应指南：

| 目标 | 推荐页面 |
| --- | --- |
| 查找本地文件、目录、URL 或业务数据源 | {doc}`/guide/finding/index` |
| 探索 GRIB 元数据并选择字段 | {doc}`/guide/grib/index` |
| 将 GRIB 字段转换为 xarray | {doc}`/guide/grib/xarray-output` |
| 进行区域截取、站点采样或网格插值 | {doc}`/guide/processing/index` |
| 了解旧 API 到新 API 的迁移方式 | {doc}`/guide/migration` |

本章节使用的测试数据不要求 CMA 或 CMADaaS 凭据。访问实际业务数据时，请先阅读相应
数据源指南中的环境、挂载目录和认证要求。

```{toctree}
:maxdepth: 1

installation
test-data
first-workflow
```
