顶层 reki
=========

公开来源以 mapping 构造；Query / Request 和结构化错误使用 cedarkit-query 的唯一 v1。
此页显式列出惰性重导出，避免静态 autodoc 扫描漏掉 __getattr__ 提供的成员。

.. autofunction:: reki.from_source
   :no-index:

.. autofunction:: reki.load_catalog
   :no-index:

.. autofunction:: reki.normalize_data_array
   :no-index:

.. autofunction:: reki.validate_data_array
   :no-index:

.. autofunction:: reki.register
   :no-index:

.. autoclass:: reki.Query
   :no-index:

.. autoclass:: reki.Request
   :no-index:

.. autoclass:: reki.QueryError
   :no-index:

.. autoclass:: reki.SourceError
   :no-index:

.. autoclass:: reki.CompletenessError
   :no-index:

.. autoclass:: reki.QueryReport
   :no-index:

.. autoclass:: reki.QueryExplanation
   :no-index:

.. autoclass:: reki.ReaderCapabilities
   :no-index:

.. autoclass:: reki.Source
   :no-index:

数组算子见 :doc:`operators` （ ``operator`` 模块），内部格式插件与资料工具见 :doc:`sources`。
