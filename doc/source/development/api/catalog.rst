产品目录与资源构造
==================

阶段 1.1 I04 使用 cedarkit-query 公共模型。配置加载可以读取显式资源文件；不会导入
reader、扫描业务文件或调用服务。接口与未完成边界见
:doc:`../architecture/catalog-and-plugins`。

.. automodule:: reki.catalog
   :members:
   :member-order: bysource

.. automodule:: reki.catalog.query_binding
   :members:
   :member-order: bysource

``plan_source_binding`` 是内部构造接口，不执行 Query。当前内置目录仅登记已知数据集身份，
产品／业务版本及真实绑定尚待证据补全。旧 catalog CLI 的消费改造由 I08 承接，本次不宣称
CLI 或完整业务读取已迁移。
