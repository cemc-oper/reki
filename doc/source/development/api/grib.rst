GRIB 与参数解析
===============

GRIB reader、参数 registry/resolver 和消息级辅助函数。持久 index 是内部实现，
只在 :doc:`../architecture/grib-reader-and-index` 中说明。

.. automodule:: reki.readers.grib
   :members:
   :member-order: bysource

.. automodule:: reki.readers.grib.config
   :members:
   :member-order: bysource

.. autodata:: reki.readers.grib.config.WHEN_KEYS

.. autofunction:: reki.readers.grib.config.check_value

.. autofunction:: reki.readers.grib.config.find_cemc_name

.. autofunction:: reki.readers.grib.config.find_short_name

.. autofunction:: reki.readers.grib.config.find_wgrib2_name

.. autofunction:: reki.readers.grib.config.get_param_registry

.. autofunction:: reki.readers.grib.config.get_parameter_index

.. automodule:: reki.readers.grib.eccodes
   :members:
   :member-order: bysource

公共查询定位
------------

``reki.query_locator`` 从 T08 的受控 ``BindingPlan`` 展开有限查询，并通过现有
GRIB index 或头扫描执行 ``list_fields`` / ``locate_fields``；两者不解码 values。
本地结果分别报告 ``not_found``、``path_exists`` 或 ``field_confirmed``，天擎
绑定只报告 ``remote_unverified``，不访问服务。调用方须显式提供稳定参数 ID 到
原生 GRIB shortName 的映射；选择成员时还须提供 ID 到角色的映射。未核验的层次、
网格和 coverage 条件报 ``unsupported``。

返回的 ``LocatedItem``、``DataReference`` 与 ``ListedField`` 含受控文件路径，不能直接用于公开
日志。``verify_data_reference`` 可从 JSON/dict 回读引用，检查本地文件的
size、mtime_ns、device、inode 指纹；``locate_fields(hash_resources=True)``
另存 SHA256，并在回读时核对文件内容。文件变化报 ``stale_reference``。四元指纹
无法证明文件在相同元数据下未被改写；严格内容核验会额外读取整个文件，但不解码
GRIB values。``reki-local`` 解析需要调用方提供
配置目录，并由调用方保证 T08 的 ``config_version`` 对应所选配置。

.. automodule:: reki.query_locator
   :members:
   :member-order: bysource
