# 准备测试数据

快速开始使用内置 `test` source 的冻结 `ecmwf_ifs` 数据集：它是固定时次和内容的
ECMWF IFS 0.25° 子集，适合可重复执行的示例。不要用滚动的 `cma_gfs` 数据集编写
文档或验证示例。

在安装 reki 的 uv 环境中下载默认东亚域数据：

```bash
uv run reki-test-data download ecmwf_ifs
```

区域处理示例还需要全球域时，额外下载：

```bash
uv run reki-test-data download ecmwf_ifs --domain global
```

下载默认写入共享临时缓存；已存在的文件会跳过，下载一次后可离线使用。详细的数据集
范围、版本语义和 CC-BY-4.0 署名见 {doc}`/getting-started/test-data`。
