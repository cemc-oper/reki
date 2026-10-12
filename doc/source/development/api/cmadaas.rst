CMADaaS
=======

请求绑定在网络访问前验证 source、参数和时间。inventory CLI 只扫描 metadata，
不读取 GRIB values。

.. automodule:: reki.cmadaas_request
   :members:
   :member-order: bysource

冻结公共查询执行
----------------

``reki.query_cmadaas`` 将 T08 的 CMADaaS ``BindingPlan`` 与 T07 的冻结参数
映射接到既有 ``model_grid`` 高层调用。``plan_frozen_cmadaas`` 只计算请求，
不导入可选客户端或访问服务；``read_frozen_cmadaas`` 才执行请求，并接受
调用方提供的客户端以便离线验证。两者要求当前冻结注册表 SHA256、目录
``cma_gfs_gmf_cmadaas`` 与 dataCode
``NAFP_FOR_FTM_GRAPES_GFS_25KM_GLB``。

支持范围仅为 2026-08-30 00Z 起报、+24h、地面场和历史北京矩形
``39–41°N, 115–117°E``。``cedarkit.t/TEM`` 与
``cedarkit.h.any/GPH`` 为瞬时场；``cedarkit.rainc.any/CPE`` 与
``cedarkit.rainnc.any/LPE`` 为已核验的 0–24h 累计场。MUSIC 无独立统计窗
参数，因此累计窗只允许与这两个无后缀产品代码配对；错误窗口会在请求前失败。
地面场按历史请求明确传 ``levelType=1``、``fcstLevel=0``，不把地面层条件
静默丢弃。成员、压力层、多字段组合、显式 coverage、新时效及其他 dataCode
均不在首版支持范围。

高层客户端负责接口选择、服务调用和响应转为 ``xarray.DataArray``。reki
核验单个非空纬经度网格及响应参数名，保留客户端返回的数值、坐标和单位，
不做单位换算或重网格化。结果保留已执行请求与 query/binding 身份；没有
远端资源版本，不进入本地 GRIB 缓存。服务失败映射为 ``provider_error``，
未将未知服务错误猜成资料缺失。离线测试使用合成响应对象，不能替代真实
天擎服务可达性验证。

.. automodule:: reki.query_cmadaas
   :members:
   :member-order: bysource

.. automodule:: reki.cmadaas_inventory
   :members: build_inventory

命令
----

``reki cmadaas-inventory --manifest PATH --root PATH --output PATH`` 生成确定性的
metadata inventory。它要求 manifest 和 ready 样本位于本地；不会调用 CMADaaS 服务。
