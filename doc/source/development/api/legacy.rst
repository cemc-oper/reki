兼容 API
========

这些入口保持兼容，但新代码应使用 :doc:`sources`、:doc:`readers` 和
:doc:`operators` 中的推荐 API。

.. automodule:: reki.data_finder
   :members:

.. automodule:: reki.format.grib
   :members:

``reki.format.grib.cfgrib`` 的 ``load_field_from_file`` 与
``load_fields_from_file`` 仍为兼容入口；其历史 docstring 不符合当前 Sphinx 的
reStructuredText 规则，因此完整签名以源码和 :doc:`public-api-inventory` 为准。

.. automodule:: reki.format.grib.common
   :members:

.. automodule:: reki.format.grib.eccodes
   :members:

.. automodule:: reki.format.grib.eccodes.bytes
   :members:

.. automodule:: reki.format.grib.eccodes.operator
   :members:

.. automodule:: reki.format.grads
   :members:

.. automodule:: reki.format.netcdf
   :members:

.. automodule:: reki.format.table
   :members:

.. automodule:: reki.format.grib.config
   :members:
