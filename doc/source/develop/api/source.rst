数据源与读取器
==================================

统一入口
----------

.. py:currentmodule:: reki

.. autofunction:: from_source

.. autofunction:: from_source_lazily

.. autofunction:: register

数据源
----------

.. autoclass:: reki.Source
   :members:

内置数据源：

.. autoclass:: reki.sources.test.TestSource
   :members:

.. autoclass:: reki.sources.file.FileSource
   :members:

.. autoclass:: reki.sources.url.UrlSource
   :members:

.. autoclass:: reki.sources.memory.MemorySource
   :members:

.. autoclass:: reki.sources.local.LocalSource
   :members:

读取器
----------

.. autoclass:: reki.readers.Reader
   :members:

.. autoclass:: reki.readers.grib.reader.GribReader
   :members:

数据处理
----------

.. currentmodule:: reki.operator

.. autofunction:: extract_region

.. autofunction:: extract_point

.. autofunction:: interpolate_grid

.. autofunction:: sample_nearest
