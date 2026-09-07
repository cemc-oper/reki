用户指南
==========

reki 使用统一数据访问模型：``source → query / metadata → data object →
processing``。先通过 source 定位数据，再用查询和元数据确定字段；只有转换为
数据对象时才读取值，随后使用处理操作。新代码应使用推荐 API；旧 API 仅在兼容章节
使用，完整对照见 :doc:`migration`。

.. toctree::
   :maxdepth: 1

   finding/index
   loading/index
   processing/index
   migration


.. toctree::
   :maxdepth: 2
   :caption: 旧 API（兼容层）

   legacy_find
   legacy_finder_config
   legacy_grib
