# 准备测试数据

本文档使用内置 `test` source 的冻结 `ecmwf_ifs` 数据集。
该数据集是由 [cemc-oper/cedarkit-test-data](https://github.com/cemc-oper/cedarkit-test-data) 项目根据 ECMWF IFS 开放数据制作的一系列小文件，用于进行自动化测试，包括：

## 下载 ecmwf_ifs 数据集

在安装 reki 的 uv 环境中下载默认东亚域数据：

```bash
uv run reki-test-data download ecmwf_ifs
```

区域处理示例还需要全球场时，额外下载：

```bash
uv run reki-test-data download ecmwf_ifs --variant global
```

可以下载 ecmwf_ifs 的全部样例数据：

```bash
uv run reki-test-data download ecmwf_ifs --all
```

数据默认被下载到 `/tmp/cedarkit-test-data/` 目录中。

## 下载 cma_gfs 数据集

reki-test-data 也支持从 CMA 的 WIS 网站下载 CMA-GFS 数据。

```bash
uv run reki-test-data download cma_gfs
```