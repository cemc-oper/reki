# 命令行

`reki inspect`、`reki ls` 与 `reki query` 面向本地 GRIB 文件，且只读取 header。先下载
或指定已有文件；以下以发布的 core 资产为例：

```console
$ reki inspect ifs_eastasia_2026090712_f024.grib2 --json
$ reki ls ifs_eastasia_2026090712_f024.grib2 --parameter t --level-type isobaricInhPa --keys parameter,level --json
$ reki query ifs_eastasia_2026090712_f024.grib2 --parameter t --level 850 --json
```

`query` 未匹配时使用非零退出码，便于脚本显式处理；`ls` 仍可用于查看空结果：

```console
$ reki query ifs_eastasia_2026090712_f024.grib2 --parameter does-not-exist --json
# exits with status 4 (no matching fields)
```

对重复检查使用 `--use-index --index-dir .reki-index`；只读部署使用
`--read-only-index`。`--verbose` 会把 index 命中和重建诊断写到 stderr，不污染 JSON stdout。
