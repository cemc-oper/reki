CMADaaS 公共查询
========================

使用声明式 ``kind="cmadaas"`` 来源和当前公共 Query / Request。注册产品、响应核验、
单位证据和已接受的服务范围见 :doc:`/guide/cmadaas-query`。

旧 cmadaas_request / query_cmadaas / cmadaas_inventory 模块及旧绑定协议已退出。
explain 不访问服务，实际读取才请求；服务错误、认证、超时与解码错误使用公共
SourceError 分类，正常无资料和未知异常不能互相替代。此页不扩大已登记服务能力。
