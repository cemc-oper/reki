GRIB 读取与公共查询
===================

公共 source mapping、Query / Request、Field / Fields 的组织与报告见
:doc:`/guide/public-query`。历史 query_locator / query_collection / CollectionSession
协议已退出，不作为当前入口。持久索引不被读取链使用。

.. automodule:: reki.readers.grib
   :members:
   :member-order: bysource

.. automodule:: reki.readers.grib.eccodes
   :members:
   :member-order: bysource

受保护函数的首匹配、多层、消息所有权和低频公共组织分别见
:doc:`/guide/legacy_grib`；内部格式分派不提供第二套公开 SDK。
