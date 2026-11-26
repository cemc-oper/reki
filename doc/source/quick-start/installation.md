# 安装

reki 支持 Python 3.11 及更高版本。本文档使用 `reki.from_source({...})` 声明数据来源，
并使用 Query / Request v1 选择字段。

在支持的平台上，GRIB2 解码所需的 ecCodes 随依赖安装。

## 从源码安装

要运行本文档的示例，请在对应的源码检出中安装 reki。在已激活的 Python 虚拟环境中，
从仓库根目录运行下面的命令。

```bash
python -m pip install .
```

也可以用 uv 创建环境并从 PyPI 解析依赖。

```bash
uv venv
uv pip install --no-sources .
```

激活该环境后即可运行示例中的 Python 和 `reki-test-data` 命令。

## 安装 PyPI 发布版

在已有项目中，可从 PyPI 安装发布版。使用与所装版本对应的文档，
版本列表见 [GitHub Releases](https://github.com/cemc-oper/reki/releases)。
从旧 API 升级时参考 {doc}`/guide/migration`。

```bash
python -m pip install reki
```

在 uv 项目中也可以运行 `uv add reki`。

## 可选依赖

- `cmadaas` 安装访问 CMADaaS MUSIC 所需的客户端。连接与凭据配置见 {doc}`/guide/cmadaas-query`。
- `lazy` 安装 Dask，以供支持惰性读取的 reader 使用。

从源码安装时使用 `python -m pip install '.[cmadaas,lazy]'`，从 PyPI 安装时使用
`python -m pip install 'reki[cmadaas,lazy]'`。按需选择其中一个或两个 extra。

继续阅读 {doc}`test-data`，下载示例所用的公开 GRIB2 数据。
