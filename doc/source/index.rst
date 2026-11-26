reki
====

reki 是一个用于查找、读取、查询和处理气象数据的 Python 工具库。

reki 主要支持 GRIB2 格式数据。通过来源和查询声明选择字段、查看元数据，并将所选字段
转换为 ``xarray.Dataset``，再按变量获取 ``xarray.DataArray``。

reki 提供以下功能：

* 从 GRIB2 文件中加载要素场，支持按参数、层次、起报时间、预报时效和其他 GRIB 键进行筛选；
* 通过各自的 reader 读取 NetCDF、GrADS 和表格文件；NWPC 观测表格保留兼容函数；
* 支持探索 GRIB2 文件元数据；
* 提供区域截取、站点采样和网格插值等功能；
* 支持在中国气象局国家级气象超算平台 (CMA-HPC2023) 访问业务系统本地文件 (/g3/COMMONDATA)；
* 支持从气象大数据云平台 (CMADaaS) 获取业务系统数据。

快速开始
----------

先安装 reki，并准备文档使用的冻结测试数据：

* :doc:`/quick-start/installation`：安装要求和可选依赖；
* :doc:`/quick-start/test-data`：下载可重复使用的测试数据。

将 ``forecast.grib2`` 替换为下载的样例文件路径，即可读取 2 米气温。

.. code-block:: python

    from reki import from_source

    with from_source({"kind": "file", "path": "forecast.grib2"}) as source:
        t2m = source.sel(parameter="t2m").one().to_xarray()["t2m"]

完整示例见 :doc:`/quick-start/first-workflow`。

文档导航
--------

* :doc:`/guide/finding/index`：查找本地文件、URL、目录和业务数据源；
* :doc:`/guide/grib/index`：探索 GRIB 元数据、选择字段、处理层次和时效；
* :doc:`/guide/processing/index`：区域截取、站点采样和网格插值；
* :doc:`/guide/grib/cli`：使用 ``reki inspect``、``reki ls`` 和 ``reki query``；
* :doc:`/development/index`：架构、扩展、贡献和 API 参考。


公共 ``reki request`` 本地字段定位与集合读取目前只执行 GRIB；NetCDF、GrADS、
表格和 NWPC 观测表格继续使用各自的 reader 或兼容函数。各格式的查询和输出能力
见 :doc:`/guide/loading/index`。

.. note::

   本文档仅使用公开的 ECMWF IFS 数据，由 `cemc-oper/cedarkit-test-data`_ 项目制作成小文件数据集。

   如果想查看 reki 使用 CEMC 业务系统数据的示例，请访问以下两个使用实际业务系统数据生成的文档：

   * data-notebook_
   * cedarkit-notebook_

.. toctree::
   :maxdepth: 1
   :hidden:

   快速开始 <quick-start/index>
   指南 <guide/index>
   开发 <development/index>


.. _cemc-oper/cedarkit-test-data: https://github.com/cemc-oper/cedarkit-test-data
.. _data-notebook: https://data-notebook.perillaroc.wang
.. _cedarkit-notebook: https://cedarkit-notebook.perillaroc.wang
