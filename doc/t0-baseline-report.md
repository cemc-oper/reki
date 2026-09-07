# T0 基线报告

日期：2026-09-07  
范围：`repo/reki` 的文档源、文档构建配置和当前受支持导出面；未修改运行时代码、主题或已有页面结构。

## 构建基线

当前文档的标准入口是：

```bash
make -C doc data
make -C doc clean html SPHINXOPTS="-W --keep-going"
```

本次在未安装文档依赖的当前工作环境执行了较小的诊断命令：

```bash
make -C doc clean html SPHINXOPTS="--keep-going"
```

结果：失败，退出码为 `2`；`make` 在清理阶段找不到 `sphinx-build`（`/bin/sh: 1: sphinx-build: not found`），因此尚未产生可归因于本次源文件的 Sphinx warning、notebook 执行结果或链接检查结果。`doc/requirements.txt` 当前声明 `sphinx`、`sphinx-book-theme>=1`、`myst-nb` 和 `ipykernel`；安装该集合以及准备 `make data` 所需的冻结数据，是重跑严格基线的前置条件。T0 不提前变更 T1 负责的依赖或主题。

`make data` 会调用 `reki-test-data download ecmwf_ifs` 及其 global 域版本，属于下载动作；本次没有执行，以免把“依赖/数据尚未准备”掩盖为构建结果。Python 环境和文档依赖统一由 `uv` 管理：先使用 `uv pip install -r doc/requirements.txt` 准备环境，再通过 `uv run sphinx-build ...`（或在同一 uv 环境内执行 `make`）重跑基线；不使用系统 Python 或手工激活环境。

## 当前配置与页面清单

- 构建配置：`doc/source/conf.py` 使用 `sphinx_book_theme`，启用 `sphinx.ext.napoleon`、`sphinx.ext.autodoc` 和 `myst_nb`，并设置 `nb_execution_mode = "force"`。
- 文档源共有 20 个内容页面：首页 1 个，`getting-started/` 4 个，`guide/` 11 个，`develop/api/` 4 个。
- 已存在的 `doc/build/html/` 包含上述 20 个内容 HTML 页面以及 `genindex.html`、`search.html`；它是工作树中已有构建产物，不能替代本次严格构建的验收证据。

| 区域 | 当前页面 |
| --- | --- |
| 首页 | `index.rst` |
| 入门 | `getting-started/index.rst`、`installing.rst`、`quick-overview.md`、`test-data.rst` |
| 指南 | `guide/index.rst`、`data_find.rst`、`data_load.md`、`data_process.md`、`catalog.md`、`grib_parameter.md`、`grib_level.md`、`parameter_resolver.md`、`legacy_find.md`、`legacy_finder_config.md`、`legacy_grib.md` |
| 开发 API | `develop/api/index.rst`、`source.rst`、`data_finder.rst`、`grib.rst` |

## 链接基线

对源文件中的 `:doc:`、`{doc}` 和 Markdown 相对文档链接做了静态清点。现有 36 个跨页引用均指向当前 source tree 中的页面；未发现可由路径解析直接确定的失效内部文档目标。由于 Sphinx 不可用，以下检查尚未执行，必须在依赖准备后以严格构建补齐：标签/引用解析、autodoc 导入、MyST-NB 单元执行、静态资源检查，以及网络外链的 `linkcheck`。

现有 API 页面仅覆盖 source、data finder 和一小部分 GRIB；其中 `develop/api/grib.rst` 仍引用旧兼容路径。T4 应以公开 API 清单为准重组，而非直接扩张该页面。

## T0 结论与后续输入

`source/development/api/public-api-inventory.md` 已建立为后续 API 参考的唯一审计输入。它明确记录了当前没有 `__all__` 的公开候选/边界缺口，避免 T4 将所有非下划线名称误生成为 API。T1 完成依赖迁移后，应重跑本报告中的严格命令并更新“构建基线”和“链接基线”两节的实际 warning/失败列表。

### 后续验证（T1，2026-09-07）

T1 已在 uv 管理的环境中重跑严格构建：

```bash
UV_CACHE_DIR=/tmp/reki-uv-cache uv run --no-sync make -C doc clean html SPHINXOPTS='-W --keep-going'
```

PyData Sphinx Theme 构建成功，零 Sphinx warning，且所有 MyST-NB 单元执行成功。
这条结果是迁移后的验证记录；本报告上文的 `sphinx-build` 缺失结果仍保留为 T0
开始时的环境基线。
