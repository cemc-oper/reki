# 贡献指南

实现变更应保持在对应子包，并同时更新测试和受影响的文档。Python 环境使用 uv；文档变更
先安装文档依赖，再进行严格构建。

```bash
uv sync --no-default-groups --group docs
UV_CACHE_DIR=/tmp/reki-uv-cache uv run --no-sync make -C doc clean html SPHINXOPTS='-W --keep-going'
```

新增公开导出时先更新 :doc:`api/public-api-inventory` 和相应 API 页；新增 source/reader
遵循 {doc}`extending/sources` 与 {doc}`extending/readers`。提交前运行受影响 package 的
pytest；不要提交 notebook 输出、构建产物、凭据或自动生成的参数注册表。
