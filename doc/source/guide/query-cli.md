# 版本化请求 CLI

`reki request validate|plan|list|locate|read` 接收 `cedarkit.request/v1` 请求，标准输出为一行 JSON `cedarkit.response/v1`。输入可从 `--input FILE` 或 stdin（默认 `-`）读取；`--input-format` 可选 `auto`（JSON 或 YAML）、`json`、`yaml`、`text`。文本语法只覆盖 `cedarkit-query/docs/text-v1.md` 定义的受限子集；每个子命令要求输入中的 `action` 与命令一致。`RequestList` 对前四个动作按原顺序输出响应数组，`read` 仅接受单请求。

`validate` 只做结构验证，不加载目录或读取资料。`plan` 加载显式目录快照并返回规范请求、展开项、受控绑定摘要及版本，不检查文件。`list` 扫描候选文件的原生字段头；`locate` 确认字段并返回 `DataReference`，不会解码 values。远端 `list/locate` 仅返回 `unknown/remote_unverified`，不会访问服务。`read` 解码值，要求请求 `options.output={"format":"netcdf","path":"..."}`；成功 JSON 只包含产物位置和引用，数组写入 NetCDF。旧 `inspect`、`ls`、`query`、`catalog` 命令继续可用。

## 可复现的本地例子

从 `repo/reki` 执行，T09 生成器只在指定的仓库外目录创建合成 GRIB2：

```bash
uv run --offline --group test python tests/fixtures/t09/generate.py --output-dir /tmp/reki-t14
cat > /tmp/reki-t14/catalog.yaml <<'YAML'
api_version: reki.catalog/v1
datasets:
  - id: grid
    source:
      name: file-pattern
      args: [/tmp/reki-t14/baseline, 'f{forecast_hour_label}_m1.grib2']
YAML
cat > /tmp/reki-t14/locate.json <<'JSON'
{"api_version":"cedarkit.request/v1","action":"locate","query":{"api_version":"cedarkit.query/v1","domain":"grid","dataset":"grid","parameter":"cedarkit.t","reference_time":"2026-08-30T00:00:00Z","lead_time":"PT24H","vertical":{"type":"isobaric","unit":"Pa","values":85000},"statistic":{"kind":"instant"},"member":{"id":"1","role":"perturbation"}}}
JSON
uv run --offline reki request validate --input-format text <<'TEXT'
VALIDATE dataset=grid parameter=cedarkit.t
TEXT
uv run --offline reki request --catalog /tmp/reki-t14/catalog.yaml --native-parameter cedarkit.t=t --member-role 1=perturbation locate --input /tmp/reki-t14/locate.json
```

`locate` 返回的 `references[0]` 与 Python `locate_fields(plan, native_parameters={"cedarkit.t":"t"}, member_roles={"1":"perturbation"}, index_policy="off")` 的引用一致。`--native-parameter` 和 `--member-role` 都是显式数据集映射，不从词表或文件名猜测。省略 `--catalog` 时仅加载内置目录；显式目录使用文件内容 SHA256 作版本，也可用 `--catalog-version` 指定版本。`reki-local` 还需 `--local-config-version` 和 `--local-config-dir`。默认 `--index-policy off` 不创建磁盘索引；可显式选择 `auto/readonly/refresh` 和 `--index-dir`。

本地 file-pattern 的 `list` 至少需要起报时间和时效以解析有限文件；只有 dataset 的请求会明确报 `unsupported`。远端 `list` 可仅给 dataset，但结果是 `unknown`，不会访问服务。

要读取，请将同一 JSON 请求的 `action` 改为 `read`，并加入 `"options":{"output":{"format":"netcdf","path":"/tmp/reki-t14/field.nc"}}`，然后以相同目录/原生映射选项运行 `reki request ... read --input FILE`。CLI 从受控 file-pattern 绑定解析有限候选路径；成员分文件或其他候选集合可重复传 `--candidate PATH`。输出使用临时文件原子替换目标文件，响应中带 `artifact` 和逐字段 `references`。未完成组合若允许 `policy.missing="partial"`，返回 `partial` 和 `missing`，不创建伪完整产物。

## 错误与边界

解析/版本/请求错误退出码 2；缺项和未知目录/参数为 3；不支持条件、重复或需确认的未知可用性为 4；提供方、权限和资源变化错误为 5。失败的 stdout 仍是 `ok:false` 的 Response，含稳定 `error.code`、JSON Pointer `path` 和无凭据的 `context`。例如上例把层值改为 `70000` 时，默认 `locate` 返回 `not_found`、退出码 3；改为 `policy.missing="partial"` 时返回 `status:"partial"`，`details.items[0].verification="path_exists"`。

CLI `read` 不执行公共 `transforms`；请求带变换会在读数前报 `unsupported`。CMADaaS 的 `read` 仅覆盖 T13 四条冻结案例，需显式 `--registry-sha256`，并使用现有客户端访问服务；离线 `plan/list/locate` 不访问服务。没有服务版本的远端引用保持未核验，不进入本地 GRIB 缓存。
