reki
====

reki 是一个用于查找、读取、查询和处理气象数据的 Python 工具库。

reki 当前主要支持 GRIB2 格式数据，通过统一的 ``source → reader → field query`` 模型定位数据、查询元数据，并在需要时将选定
字段转换为 ``xarray.DataArray``。

reki 提供以下功能：

* 从 GRIB2 文件中加载要素场，支持按参数、层次、起报时间、预报时效和其他 GRIB 键进行筛选；
* 支持探索 GRIB2 文件元数据；
* 提供区域截取、站点采样和网格插值等功能；
* 支持在中国气象局国家级气象超算平台 (CMA-HPC2023) 访问业务系统本地文件 (/g3/COMMONDATA)；
* 支持从气象大数据云平台 (CMADaaS) 获取业务系统数据。

快速开始
----------

先安装 reki，并准备文档使用的冻结测试数据：

* :doc:`/quick-start/installation`：安装要求和可选依赖；
* :doc:`/quick-start/test-data`：下载可重复使用的测试数据。

准备好 ``ecmwf_ifs`` 测试数据后，下面的代码可以选择并加载 2 米温度：

.. code-block:: python

    from reki import from_source

    source = from_source("test", "ecmwf_ifs")
    field = source.sel(
        parameter="2t",
        level_type="heightAboveGround",
        level=2,
    ).first()
    t2m = field.to_xarray()

完整示例见 :doc:`/quick-start/first-workflow`。

文档导航
--------

* :doc:`/guide/finding/index`：查找本地文件、URL、目录和业务数据源；
* :doc:`/guide/grib/index`：探索 GRIB 元数据、选择字段、处理层次和时效；
* :doc:`/guide/processing/index`：区域截取、站点采样和网格插值；
* :doc:`/guide/grib/cli`：使用 ``reki inspect``、``reki ls`` 和 ``reki query``；
* :doc:`/development/index`：架构、扩展、贡献和 API 参考。


当前 reki 仅提供 GRIB2 格式支持，其他格式正在开发中。

.. note::

   本文档仅使用公开的 ECMWF IFS 数据生成，由 `cemc-oper/cedarkit-test-data`_ 项目制作。

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
