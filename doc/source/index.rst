reki
====

**reki**（前称 **nwpc-data**）是一个用于查找、读取、查询和处理气象数据的 Python 工具库。
当前文档和推荐工作流以 GRIB2 为主要对象：reki 通过统一的 ``source → reader → field query`` 模型定位数据、查询元数据，并在需要时将选定
字段转换为 ``xarray.DataArray``。

reki 适合以下任务：

* 从本地文件、URL 或业务数据源打开气象数据；
* 按参数、层次、起报时间、预报时效和其他 GRIB 键选择字段；
* 在解码数值前探索文件元数据，减少不必要的 I/O；
* 将结果交给 xarray，并进行区域截取、站点采样和网格插值；
* 使用 Python API 或 ``reki`` 命令行工具完成查询和检查。

快速开始
----------

先安装 reki，并准备文档使用的冻结测试数据：

* :doc:`/quick-start/installation`：安装要求和可选依赖；
* :doc:`/quick-start/test-data`：下载可重复使用的测试数据；
* :doc:`/quick-start/first-workflow`：完成查找、加载和处理的第一个 GRIB2 工作流。

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

完整示例还会检查坐标、维度并执行区域截取；它不需要 CMA 内网、业务账号或当天的预报文件，见 :doc:`/quick-start/first-workflow`。

文档导航
--------

* :doc:`/guide/finding/index`：查找本地文件、URL、目录和业务数据源；
* :doc:`/guide/grib/index`：探索 GRIB 元数据、选择字段、处理层次和时效；
* :doc:`/guide/processing/index`：区域截取、站点采样和网格插值；
* :doc:`/guide/grib/cli`：使用 ``reki inspect``、``reki ls`` 和 ``reki query``；
* :doc:`/development/index`：架构、扩展、贡献和 API 参考。

GRIB2 是当前最完整、最推荐的使用路径。其他格式和业务数据源的支持范围，可能取决于对应 reader、运行环境、挂载目录或服务凭据；
请以相应指南中的说明为准。

.. toctree::
   :maxdepth: 1
   :hidden:

   快速开始 <quick-start/index>
   指南 <guide/index>
   开发 <development/index>
