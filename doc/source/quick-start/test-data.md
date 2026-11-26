# 准备测试数据

本文档使用 `ecmwf_ifs` 数据集。它是一组基于 ECMWF IFS 开放数据制作的 GRIB2 样例，
由 [cedarkit-test-data](https://github.com/cemc-oper/cedarkit-test-data) 提供。

## 下载 ecmwf_ifs 数据集

激活已安装 reki 的环境，然后下载默认的东亚样例。

```bash
reki-test-data download ecmwf_ifs
```

需要全球场时，下载 `global` 样例。

```bash
reki-test-data download ecmwf_ifs --variant global
```

用 `--all` 下载全部 `ecmwf_ifs` 样例。

```bash
reki-test-data download ecmwf_ifs --all
```

数据默认下载到 `/tmp/cedarkit-test-data/`。下载完成后可运行 {doc}`first-workflow`。

## 下载 cma_gfs 数据集

reki-test-data 也支持从 CMA 的 WIS 网站下载 CMA-GFS 数据。

```bash
reki-test-data download cma_gfs
```
