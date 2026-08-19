用户指南
==========

本章节提供 **reki** 库更详细的说明和示例，介绍 **reki** 库可以实现的常见功能。

内容分为两部分：**新 API** 章节介绍 ``from_source()`` / ``sel()`` /
``to_xarray()`` 数据访问体系，是新代码的推荐写法；**旧 API（兼容层）**
章节完整保留 ``reki.data_finder`` / ``reki.format.grib`` 的用法说明，
供维护旧代码参考。两套 API 的对应关系见
:ref:`新旧 API 对照 <data_find_legacy_mapping>`。

.. toctree::
   :maxdepth: 2
   :caption: 新 API

   data_find
   data_load
   grib_parameter
   grib_level
   data_process

.. toctree::
   :maxdepth: 2
   :caption: 旧 API（兼容层）

   legacy_find
   legacy_finder_config
   legacy_grib