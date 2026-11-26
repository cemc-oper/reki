# 贡献指南

在仓库根目录用 uv 创建环境。文档检查使用与 CI 相同的 `--no-sources` 安装方式，
从 PyPI 解析依赖，适用于单独检出的 reki 仓库。

```bash
uv venv
uv pip install --no-sources --group docs .
uv run --no-sync make -C doc check SPHINXOPTS='-W --keep-going'
```

检查会下载并校验公开样例，运行示例，构建文档，再检查 API 参考、拼写和链接。

修改代码时同步更新受影响的测试和文档。可用
`uv pip install --no-sources --group test -e .` 安装测试依赖，再用
`uv run --no-sync pytest` 运行受影响的测试。新增公开导出时更新
{doc}`api/public-api-inventory` 和相应 API 页。新增来源或 reader 时参阅
{doc}`extending/sources` 与 {doc}`extending/readers`。
提交时排除 notebook 输出、构建产物、凭据和自动生成的参数注册表。
