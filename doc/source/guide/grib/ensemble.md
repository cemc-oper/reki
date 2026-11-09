# 集合预报

公共 Query 使用整数 member 和显式 member_role；二者来自已解析的原始集合身份。
不把所有确定性预报自动标成控制成员。已接受的 GEPS 控制 0 / 扰动 1–3 子集使用公共
来源及显式业务成员映射；完整集合分母不由实际到达文件反推。

```python
fields = source.sel(time="2026-11-02T12:00:00Z", step="PT24H", member=[1, 2, 3]).all()
dataset = fields.to_xarray()
```

公共输出的数值成员轴为 `member`，角色为独立身份；旧高频原生输出可保留 `number`。
MAX 是否包含控制成员、缺失策略与逐格有效数属于产品定义，不能由读取函数默认决定。
集合缺场和歧义遵循普通 QueryError / 完整性契约，不使用旧 one_or_none。
