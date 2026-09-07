# T5 验收报告

日期：2026-09-07  
范围：文档质量门禁、持续集成与已生成 HTML 的桌面/窄屏可用性。

## 自动化检查

所有 Python 命令均在 uv 管理的环境中执行：

```bash
UV_CACHE_DIR=/tmp/reki-uv-cache uv pip install -r doc/requirements.txt
UV_CACHE_DIR=/tmp/reki-uv-cache uv run --no-sync make -C doc data
UV_CACHE_DIR=/tmp/reki-uv-cache uv run --no-sync make -C doc clean html SPHINXOPTS='-W --keep-going'
UV_CACHE_DIR=/tmp/reki-uv-cache uv run --no-sync make -C doc api-check
UV_CACHE_DIR=/tmp/reki-uv-cache uv run --no-sync make -C doc spelling
UV_CACHE_DIR=/tmp/reki-uv-cache uv run --no-sync make -C doc linkcheck SPHINXOPTS='-W --keep-going'
UV_CACHE_DIR=/tmp/reki-uv-cache uv run --no-sync pytest -m 'not needs_data and not cma_hpc and not cmadaas_local and not cmadaas_service'
```

结果如下：

- `make data` 下载冻结的 eastasia 与 global `ecmwf_ifs` 资产；
- 严格 HTML 构建了 68 个页面，零 Sphinx warning，所有预期 MyST-NB 单元成功执行；
- `api-check` 通过。该检查读取受支持模块的显式 `__all__`，要求每个导出同时出现在
  `public-api-inventory.md` 和对应的已生成 API HTML 页面中；
- `codespell` 通过；
- `linkcheck` 通过。检查中发现并修复了已迁移的 CMADaaS 客户端 GitHub 链接；
- 环境无关 pytest：363 passed、165 deselected、13 个既有 collection/parser warning。

## 视觉与内容复核

通过 Chromium 对已生成首页分别以 1440×1000 浅色和 390×844 深色视口加载并截图。
两种视口均显示“快速开始 / 指南 / 开发”入口、搜索、主题切换和编辑入口；窄屏显示
可打开的侧栏控制项。中文正文、链接和代码块在两种颜色模式下可读；代码块在窄屏保持
自身横向滚动区域，不挤压正文布局。

复核 API 清单、渲染页面和兼容页：公开导出覆盖由自动检查持续保证，兼容页说明推荐
替代路径；旧 URL 保留为轻量兼容页。Read the Docs 配置继续安装
`doc/requirements.txt`，并在构建前下载与本地相同的冻结数据，因此依赖和执行路径一致。

## 后续事项

没有阻断验收的已知事项。外部链接会随第三方站点变化，CI 的 `linkcheck` 将持续检测。
