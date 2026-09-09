# 准备测试数据

快速开始使用内置 `test` source 的冻结 `ecmwf_ifs` 数据集：它是固定时次和内容的
ECMWF IFS 0.25° 子集，适合可重复执行的示例。不要用滚动的 `cma_gfs` 数据集编写
文档或验证示例。

在安装 reki 的 uv 环境中下载默认东亚域数据：

```bash
uv run reki-test-data download ecmwf_ifs
```

区域处理示例还需要全球场时，额外下载（旧 `domain` 写法仍兼容）：

```bash
uv run reki-test-data download ecmwf_ifs --domain global
```

多时效、集合成员和土壤层示例按 variant 下载：

```bash
uv run reki-test-data download ecmwf_ifs --variant time
uv run reki-test-data download ecmwf_ifs --variant ensemble
uv run reki-test-data download ecmwf_ifs --variant layers
```

未指定时等价于 `variant="core"`。`domain="eastasia"` 与
`domain="global"` 分别兼容映射到 `core` 和 `global`；不要将 `domain`
与指向不同文件的 `variant` 组合使用。

下载默认写入共享临时缓存；已存在的文件会跳过，下载一次后可离线使用。详细的数据集
范围、版本语义和 CC-BY-4.0 署名见本页下文。
