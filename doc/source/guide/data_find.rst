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
     - CMA-HPC 业务系统产品文件查找（见下文 ``local`` 数据源一节）
     - 仅 CMA-HPC 环境
   * - ``cmadaas``
     - 气象大数据云平台（CMADaaS）MUSIC 服务（见下文 ``cmadaas`` 数据源一节）
     - 需安装 ``cmadaas`` 额外依赖并配置服务

远程数据源（``url``、``cmadaas``、``test`` 首次下载）默认返回惰性代理，
首次真正使用时才发起网络请求；``from_source_lazily()`` 进一步把数据
本身也变为惰性（dask）数组，需安装 ``lazy`` 额外依赖。

扩展数据源可通过入口点（entry point）或 ``reki.register()`` 注册，
无需修改 reki 本身。

.. _data_find_local:

CMA-HPC 业务文件查找（``local`` 数据源）
=========================================

.. note::
    本节功能依赖 CMA-HPC 的共享文件系统与业务目录结构（或挂载了相应
    存储的机器，如 CMADAAS 挂载盘），**仅能在相应环境中运行**，
    以下代码块不参与文档构建执行，输出为示意。

``local`` 数据源使用内置 YAML 配置，从多种存储（CMA-HPC 主存储、
二级存储、CEMC 共享存储）中按 ``data_type`` 字符串解析业务系统产品
文件路径，并直接衔接到读取器：

.. code-block:: python

    from reki import from_source

    ds = from_source(
        "local",
        "grapes_gfs_gmf/grib2/orig",
        start_time="2021101400",
        forecast_time="24h",
    )
    da = ds.sel(parameter="t", level_type="pl", level=850).to_xarray()

``data_type`` 是配置文件的相对路径（不含后缀），内置配置覆盖
CMA-GFS、CMA-MESO、CMA-GEPS 等业务系统的 GRIB2 产品及中间文件，
也可以用 ``config_dir`` 参数指定自定义配置目录（配置文件格式见
:doc:`/guide/legacy_finder_config`，配置机制与旧 API 共用）。

CMADAAS 挂载盘与 ``data_class``
---------------------------------

每类 ``data_type`` 可以有多套存储配置，用 ``data_class`` 选择
（默认 ``"od"``，即 CMA-HPC 业务主存储）。在挂载了 CMADAAS 存储的
机器上，使用 ``data_class="cmadaas"`` 并用 ``storage_base`` 指定
挂载根目录：

.. code-block:: python

    ds = from_source(
        "local",
        "cma_gfs_gmf/grib2/orig",
        start_time="2026072500",
        forecast_time="24h",
        data_class="cmadaas",
        storage_base="/CMADAAS",
    )
    da = ds.sel(parameter="t", level_type="pl", level=850).to_xarray()

集合预报成员与其他模板变量
-----------------------------

配置文件的目录/文件名模板中声明的自定义变量，都可以作为关键字参数
传入。例如用 ``number`` 指定 CMA-GEPS 集合成员编号（0 为控制预报，
1–31 为集合成员）：

.. code-block:: python

    ds = from_source(
        "local",
        "cma_geps/grib2/orig",
        start_time="2026072500",
        forecast_time="24h",
        number=14,
        data_class="cmadaas",
        storage_base="/CMADAAS",
    )

调试与仅解析路径
-----------------------

- ``debug=True``：打印模板渲染与逐级目录查找的详细过程；
- 只需要路径、不加载数据时，可调用 ``local`` 数据源的
  ``resolve_path()`` 方法（文件不存在时返回 ``None``）：

.. code-block:: python

    from reki.sources.local import LocalSource

    source = LocalSource(
        "cma_gfs_gmf/grib2/orig",
        start_time="2026072500",
        forecast_time="24h",
        data_class="cmadaas",
        storage_base="/CMADAAS",
        debug=True,
    )
    file_path = source.resolve_path()

.. _data_find_cmadaas:

CMADaaS MUSIC 服务（``cmadaas`` 数据源）
=========================================

.. note::
    本节功能需要可用的 CMADaaS MUSIC 服务与账号，以下代码块不参与
    文档构建执行。注意区分两条路径：MUSIC 服务检索（本节，
    通过网络请求数据）与 CMADAAS 挂载盘读取（上一节，
    ``local`` 数据源 + ``data_class="cmadaas"``）。

``cmadaas`` 数据源封装了 `nuwe-cmadaas
<https://github.com/nwpc-oper/nuwe-cmadaas-python>`_ 客户端，
通过 CMADaaS MUSIC 服务检索数据。使用前需安装额外依赖：

.. code-block:: bash

    pip install reki[cmadaas]

服务配置
----------

MUSIC 服务地址与账号默认从 ``~/.config/cedarkit.yaml`` 读取
（可用环境变量 ``CEDARKIT_CONFIG`` 指向其他路径），格式如下：

.. code-block:: yaml

    cmadaas:
      auth:
        user: <用户名>
        password: <密码>
      server:
        music_server: <服务地址>
        music_port: <端口>

也可以在创建数据源时用 ``config`` 参数传入配置字典或配置文件路径，
或用 ``client`` 参数传入已有的 ``CMADaaSClient`` 实例。

两种检索模式
--------------

高级模式
~~~~~~~~~

用 ``kind`` 指定语义化检索函数（模式资料
``"model_grid"`` / ``"model_point"`` / ``"model_file"``，观测资料
``"obs_station"`` / ``"obs_grid"`` / ``"obs_upper_air"`` /
``"obs_file"``），其余关键字参数透传给检索函数：

.. code-block:: python

    ds = from_source(
        "cmadaas",
        kind="model_grid",
        data_code="NAFP_GRAPESGFS_GLB",
        parameter="TMP",
        level_type="pl",
        level=850,
        start_time="2026072500",
        forecast_time="24h",
    )
    da = ds.to_xarray()

低级模式
~~~~~~~~~

直接映射 MUSIC 接口：``interface_id`` + ``params``
+ ``return_type``（``"gridArray2D"`` / ``"array2D"`` /
``"fileList"`` / ``"saveAsFile"`` / ``"downFile"``）：

.. code-block:: python

    ds = from_source(
        "cmadaas",
        interface_id="getNafpEleGrid",
        params={
            "dataCode": "NAFP_GRAPESGFS_GLB",
            "element": "TMP",
            "fcstLevel": "850",
            "time": "20260725000000",
            "fcstHour": "024",
        },
        return_type="gridArray2D",
    )
    da = ds.to_xarray()

内存结果（``gridArray2D`` 等）由 ``cmadaas`` 读取器解析为
``xarray.DataArray``；文件类结果（``fileList`` / ``saveAsFile`` /
``downFile``）自动衔接为 ``url`` / ``file`` 数据源。

.. _data_find_legacy_mapping:

新旧 API 对照
==============

reki 保留了完整的旧 API 兼容层（``reki.data_finder`` 与
``reki.format`` 命名空间），旧代码无需修改即可继续运行。旧 API 的
完整文档见 :doc:`/guide/legacy_find`、:doc:`/guide/legacy_finder_config`
与 :doc:`/guide/legacy_grib`。
下表给出旧 API 与新 API 的对应关系，新代码请使用右侧写法：

.. list-table::
   :header-rows: 1
   :widths: 45 55

   * - 旧 API（兼容层）
     - 新 API
   * - ``reki.data_finder.find_local_file(data_type, ...)``
       （见 :doc:`/guide/legacy_find`）
     - ``from_source("local", data_type, ...)``（见上文 ``local`` 数据源）
   * - ``reki.data_finder.get_local_file_name(data_type, ...)``
       （见 :doc:`/guide/legacy_find`）
     - ``local`` 数据源的 ``resolve_path()`` 方法
   * - ``reki.format.grib.load_field_from_file(path, ...)``
       （见 :doc:`/guide/legacy_grib`）
     - ``from_source("file", path).sel(...).to_xarray()``
       （见 :doc:`/guide/data_load`）
   * - ``reki.format.grib.load_fields_from_file(path, ...)``
       （见 :doc:`/guide/legacy_grib`）
     - ``from_source("file", path).sel(...).to_xarray()``
       （多层次返回带层次维的 ``Dataset``，见 :doc:`/guide/grib_level`）
   * - ``reki.format.grib.load_message_from_file(path, ...)``
       （见 :doc:`/guide/legacy_grib`）
     - ``reki.readers.grib.eccodes.load_message_from_file(path, ...)``
   * - ``reki.format.grib.config.get_param_registry()``
       （见 :doc:`/guide/legacy_grib`）
     - ``reki.readers.grib.config.get_param_registry()``
       （见 :doc:`/guide/grib_parameter`）
