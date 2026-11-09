数据源
======

这里记录内部命名格式工厂、注册和测试资料工具。公开 QuerySource 使用顶层
``reki.from_source(mapping)``，不接受旧 SourceSpec 或位置式名称。内部格式插件使用 ``reki.sources`` entry point；
扩展流程见 :doc:`../extending/sources`。

.. automodule:: reki.sources
   :members:
   :member-order: bysource
   :exclude-members: Source

.. autodata:: reki.sources.get_source

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
