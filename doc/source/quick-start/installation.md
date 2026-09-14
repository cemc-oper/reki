# 安装

reki 支持 Python 3.11 及更高版本。
推荐在项目的 uv 环境中安装。
GRIB 支持随 PyPI 的 `eccodes` wheel 一起安装，无需另行配置系统 ecCodes。

## 使用 pip 安装

使用 pip 安装：

```bash
pip install reki
```

## 使用 uv 安装

推荐使用 uv 安装。在已有 uv 项目中添加 reki：

```bash
uv add reki
```

若只需要临时环境，先创建虚拟环境再安装：

```bash
uv venv
uv pip install reki
```

## 可选依赖

- `reki[cmadaas]`：访问 CMADaaS MUSIC 服务；需要有效的服务环境与凭据。
- `reki[lazy]`：使用 dask 进行惰性数组处理。

例如：

```bash
uv add "reki[cmadaas,lazy]"
# or use pip
pip install "reki[cmadaas, lazy]"
```

首次运行前，请继续准备冻结测试数据，而不是使用 CMA 内网或滚动业务数据。
