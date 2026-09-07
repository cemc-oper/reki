数据源
======

工厂、注册和内置 source 的 API。外部 source 使用 ``reki.sources`` entry point；
扩展流程见 :doc:`../extending/sources`。

.. automodule:: reki.sources
   :members:
   :member-order: bysource
   :exclude-members: Source

内置 source
------------

.. autoclass:: reki.sources.test.TestSource
   :members:

.. autoclass:: reki.sources.file.FileSource
   :members:

.. autoclass:: reki.sources.file_pattern.FilePatternSource
   :members:

.. autoclass:: reki.sources.local.LocalSource
   :members:

.. autoclass:: reki.sources.url.UrlSource
   :members:

.. autoclass:: reki.sources.memory.MemorySource
   :members:

.. autoclass:: reki.sources.cmadaas.CmadaasSource
   :members:
