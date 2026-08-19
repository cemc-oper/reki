#############
数据查找
#############

reki 的数据访问分为两层：**数据源（source）** 负责"数据从哪里来"，
**读取器（reader）** 负责"数据怎么解析"。统一入口 ``from_source()``
把两者串起来：创建数据源 → 定型（mutate）为最具体的数据源 →
按文件内容分派读取器。

.. code-block:: python

    from reki import from_source

    ds = from_source("test", "ecmwf_ifs")     # 数据源：内置测试数据集
    field = ds.sel(parameter="2t", level_type="heightAboveGround", level=2)
    da = field.to_xarray()                     # 读取器：GRIB → xarray

内置数据源
==========

.. list-table::
   :header-rows: 1
   :widths: 15 55 30

   * - 名称
     - 说明
     - 备注
   * - ``test``
     - 内置测试数据集（``ecmwf_ifs`` 冻结数据集、``cma_gfs`` 滚动数据集），
       首次使用自动下载到共享缓存目录
     - 详见 :doc:`/getting-started/test-data`
   * - ``file``
     - 本地文件，按文件内容自动识别格式（GRIB / GrADS / NetCDF / 表格）
     - ``from_source("file", path)``
   * - ``url``
     - 远程文件 URL，先下载到本地再按 ``file`` 处理
     - 需要网络
   * - ``memory``
     - 内存中的字节流
     -
   * - ``local``
     - CMA-HPC 业务系统产品文件查找（见下文"兼容层"）
     - 仅 CMA-HPC 环境
   * - ``cmadaas``
     - 气象大数据云平台（CMADaaS）MUSIC 服务
     - 需安装 ``cmadaas`` 额外依赖并配置服务

远程数据源（``url``、``cmadaas``、``test`` 首次下载）默认返回惰性代理，
首次真正使用时才发起网络请求；``from_source_lazily()`` 进一步把数据
本身也变为惰性（dask）数组，需安装 ``lazy`` 额外依赖。

扩展数据源可通过入口点（entry point）或 ``reki.register()`` 注册，
无需修改 reki 本身。

.. _data_find_local:

本地文件查找（兼容层）
======================

.. note::
    本节功能依赖 CMA-HPC 的共享文件系统与业务目录结构，
    **仅能在 CMA-HPC 环境（及挂载了相应存储的机器）中运行**，
    以下输出为示意。

``reki.data_finder`` 是 reki 重构前的本地文件查找接口，作为兼容层保留。
它使用内置 YAML 配置，从多种存储（CMA-HPC 主存储、二级存储、CEMC 共享
存储）中按 ``data_type`` 字符串解析业务系统产品文件路径：

.. code-block:: pycon

    >>> from reki.data_finder import find_local_file
    >>> file_path = find_local_file(
    ...     "grapes_gfs_gmf/grib2/orig",
    ...     start_time="2021101400",
    ...     forecast_time="24h",
    ... )
    >>> file_path
    PosixPath('/g1/COMMONDATA/OPER/NWPC/GRAPES_GFS_GMF/Prod-grib/2021101400/ORIG/gmf.gra.2021101400024.grb2')

``find_local_file`` 接收任意在配置文件中声明的自定义参数，
例如用 ``number`` 指定集合预报成员、用 ``storage_base`` 指定挂载盘符：

.. code-block:: pycon

    >>> find_local_file(
    ...     "grapes_geps/grib2/orig",
    ...     start_time="2021101412",
    ...     forecast_time="48h",
    ...     number=20,
    ... )
    PosixPath('.../gef.gra.020.2021101412048.grb2')

在新代码中，推荐使用 ``from_source("local", data_type, ...)`` 数据源，
它内部复用同一套查找配置，并直接衔接到读取器：

.. code-block:: python

    from reki import from_source

    ds = from_source(
        "local",
        "grapes_gfs_gmf/grib2/orig",
        start_time="2021101400",
        forecast_time="24h",
    )
    da = ds.sel(parameter="t", level_type="pl", level=850).to_xarray()
