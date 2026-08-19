.. _test-data:

获取测试数据
============

reki 内置 ``test`` 数据源（source），提供开箱即用的测试数据集，
本文档站内的可执行示例均基于此数据源。
数据集命名规则为 ``<机构>_<模式>``。

滚动与冻结
----------

reki 目前提供两个数据集，语义不同，用途也不同：

.. list-table::
   :header-rows: 1
   :widths: 15 20 30 35

   * - 数据集
     - 语义
     - 内容
     - 用途
   * - ``ecmwf_ifs``
     - **冻结**：起报时次、预报时效、要素与区域固定在文件名中，
       内容不随时间变化
     - ECMWF IFS 0.25° 裁剪子集（KB～MB 级），两个区域（domain）：

       - ``eastasia``\ （默认）：2t/2d/10u/10v/msl/tp，0–60N, 60–150E
       - ``global``：仅 2t，全球场
     - **文档示例**、需要可复现结果的场景
   * - ``cma_gfs``
     - **滚动**：起报时次随日期滚动，每次获取的文件不同
     - CMA-GFS（GRAPES-GFS）全球场完整文件（数百 MB）
     - 仅供测试；**不可复现，请勿用于文档示例**

``gfs`` 是 ``cma_gfs`` 的旧名，作为别名保留。

下载工具：reki-test-data
------------------------

安装 reki 后附带 ``reki-test-data`` 命令行工具：

.. code-block:: bash

    # 冻结数据集（文档示例用），默认 eastasia 区域
    reki-test-data download ecmwf_ifs

    # 全球区域（regrid/area 等算子示例用）
    reki-test-data download ecmwf_ifs --domain global

    # 滚动数据集（仅测试用；gfs 为别名）
    reki-test-data download cma_gfs

文件默认下载到共享缓存目录 ``$TMPDIR/cedarkit-test-data``
（可用 ``-o`` 指定其他目录）。下载是幂等的：文件已存在即跳过，
首次下载后离线也可用。

在 reki 中使用
--------------

通过统一的 ``from_source`` 入口使用 ``test`` 数据源，
未下载时会自动获取（与上面的命令同一缓存目录）：

.. code-block:: python

    from reki import from_source

    ds = from_source("test", "ecmwf_ifs")
    field = ds.sel(parameter="2t", level_type="heightAboveGround", level=2)
    da = field.to_xarray()

进阶：直接引用发布地址
----------------------

冻结数据集托管在
`cedarkit-test-data 仓库的 GitHub release
<https://github.com/cemc-oper/cedarkit-test-data/releases>`_ 上，
也可以不经 ``test`` 数据源，直接用 ``url`` 数据源引用发布资产：

.. code-block:: python

    from reki import from_source

    ds = from_source(
        "url",
        "https://github.com/cemc-oper/cedarkit-test-data/releases/"
        "download/v2026.8.0/ifs_eastasia_2026081800_f024.grib2",
    )

数据署名
--------

``ecmwf_ifs`` 数据集包含修改后的 ECMWF IFS 开放数据，
按 CC-BY-4.0 许可要求署名如下：

    This product contains modified data from the ECMWF IFS (open data set),
    © European Centre for Medium-Range Weather Forecasts (ECMWF),
    licensed under CC-BY-4.0 (https://creativecommons.org/licenses/by/4.0/).
    Source: https://www.ecmwf.int/en/forecasts/datasets/open-data
    Modifications: subset of parameters and domain.
