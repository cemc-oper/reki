兼容 API
========

这些入口保持兼容，但新代码应使用 :doc:`sources`、:doc:`readers` 和
:doc:`operators` 中的推荐 API。

.. automodule:: reki.data_finder
   :members:
   :imported-members:
   :undoc-members:

.. automodule:: reki.format.grib
   :members:
   :imported-members:
   :undoc-members:

cfgrib 后端、命名路径与依赖已删除；显式 engine="cfgrib" 报 QueryError(unsupported)。
高频字段／消息函数与低频 Dataset 组织分别按 :doc:`/guide/legacy_grib` 保护。

.. automodule:: reki.format.grib.common
   :members:
   :imported-members:
   :undoc-members:

.. automodule:: reki.format.grib.eccodes
   :members:
   :imported-members:
   :undoc-members:

.. automodule:: reki.format.grib.eccodes.bytes
   :members:
   :imported-members:
   :undoc-members:

.. automodule:: reki.format.grib.eccodes.operator
   :members:
   :imported-members:
   :undoc-members:

.. automodule:: reki.format.grads
   :members:
   :imported-members:
   :undoc-members:

.. automodule:: reki.format.netcdf
   :members:
   :imported-members:
   :undoc-members:

.. automodule:: reki.format.table
   :members:
   :imported-members:
   :undoc-members:

``NWPC_OBS_CONFIG`` 是旧观测表格读取器使用的兼容配置映射。它保留在
``reki.format.table`` 中，新的读取流程应优先采用 :doc:`readers`。

   :members:
   :imported-members:
   :undoc-members:
