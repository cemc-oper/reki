CMADaaS
=======

请求绑定在网络访问前验证 source、参数和时间。inventory CLI 只扫描 metadata，
不读取 GRIB values。

.. automodule:: reki.cmadaas_request
   :members:
   :member-order: bysource

.. automodule:: reki.cmadaas_inventory
   :members: build_inventory

命令
----

``reki cmadaas-inventory --manifest PATH --root PATH --output PATH`` 生成确定性的
metadata inventory。它要求 manifest 和 ready 样本位于本地；不会调用 CMADaaS 服务。
