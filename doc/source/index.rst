欢迎来到 reki 文档
================================

**reki** (前称 **nwpc-data**) 是为 CMA 天气模式开发的数据准备 Python 开源工具库，提供检索要素场的便捷方法。

reki 支持 GRIB、GrADS、NetCDF、CSV 等多种数据格式，对接中国气象局 CMA-PI 高性能计算机、二级存储等多种数据来源，可在 Windows、Linux 等环境中运行。
reki 提供区域截取、插值等多种数据操作方法。

reki 能够非常方便地从 GRIB 等格式文件中加载要素场为常见的 Python 科学库格式。

.. code-block:: py

   from reki.format.grib import load_field_from_file

   file_path = "/some/path/to/data.grib2"
   field = load_field_from_file(
         parameter="t",
         level_type="pl",
         level=850
   )


.. toctree::
   :maxdepth: 2
   :caption: 用户
   :hidden:

   开始使用 <getting-started/index>
   指南 <guide/index>

.. toctree::
   :maxdepth: 2
   :caption: 开发
   :hidden:

   API <develop/api/index>
