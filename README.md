# jsondiff

语义化对比两个 JSON 文档：两个 JSON 文件进，人类可读的结构差异出。

纯 Python 标准库（`json` / `argparse` / `sys` / `difflib`），零依赖，单文件可直接拷贝走。

## 为什么不用 `diff`

`diff` 逐行比文本，JSON 里换个字段顺序、数组里删掉一个元素，整片飘红。
jsondiff 懂结构：

```
~ users[id=7].age: 30 -> 31          # 值变更
+ users[id=10]: {"age":28,...}       # 新增
- config.debug: true                 # 删除
! config.timeout: type int -> string # 类型变化
```

## 快速开始

```bash
python -m jsondiff examples/before.json examples/after.json
```

输出（路径按字母序排列，稳定可测）：

```
- config.debug: true
! config.timeout: type int -> string
~ meta.built_at: "2026-10-01T10:00:00Z" -> "2026-10-05T03:00:00Z"
~ meta.version: "1.2.0" -> "1.3.0"
+ users[id=10]: {"age":28,"email":"qiang@example.com","id":10,"name":"阿强"}
~ users[id=7].age: 30 -> 31
- users[id=8]: {"age":25,"email":"hong@example.com","id":8,"name":"小红"}
- users[id=9]: {"age":41,"email":"wang@example.com","id":9,"name":"老王"}
```

注意 `users` 数组：删了 id=8、id=9，加了 id=10，但 id=7 的变更被正确定位为
`users[id=7].age`，没有出现"下标错位导致整数组飘红"——这是本工具的核心小聪明。

## 参数

| 参数 | 说明 |
|---|---|
| `before.json after.json` | 两个要对比的 JSON 文件 |
| `--by-key KEY` | 对象数组按指定字段匹配（如 `--by-key email`）；默认依次尝试 `id` / `name` / `email` |
| `--ignore PAT` | 忽略匹配的路径（fnmatch 语法，如 `"meta.*"`），可重复指定 |
| `--json` | 输出机器可读的 JSON（`[{op, path, old, new}]`） |
| `--compact` | 紧凑输出：只显示操作符和路径，不显示值 |
| `--version` | 显示版本 |

退出码：`0` 无差异 / `1` 发现差异 / `2` 出错（文件不存在、JSON 非法等），CI 可直接用。

```bash
# 只关心业务字段，忽略元数据
python -m jsondiff before.json after.json --ignore "meta.*"

# 数组按 email 匹配（id 体系变了也能对上）
python -m jsondiff before.json after.json --by-key email

# 机器消费
python -m jsondiff before.json after.json --json | jq .
```

## 数组匹配规则

1. 数组元素**都是对象**，且某个字段（默认 `id`→`name`→`email`，或 `--by-key`
   指定）在**两边所有元素都存在、且值唯一**时，按该字段匹配，路径写作
   `users[id=7].age`。
2. 否则退化为**按下标**逐个对比，超出的部分记新增/删除。
3. 多行字符串的值变更会用 unified diff 展开显示（`difflib`）。

### 关于 `--context` 的取舍

最初考虑加 `--context` 显示变更周围的未变兄弟节点，实际写下来发现：
路径本身（`users[id=7].age`）已经给出了完整定位，再展开兄弟节点只是噪音。
**有意省略**，保持输出干净。

## 诚实说明（局限）

- key 匹配是启发式：数组元素没有稳定唯一字段时，只能按下标对比，
  删中间元素会导致后续元素"错位"报出一串变更——这是所有无 key diff 的固有问题。
- `--ignore` 用 fnmatch 匹配路径字符串；带方括号的路径段（如 `users[id=7]`）
  里 `[...]` 会被当成字符集，写 `users[*].age` 这类模式时注意，复杂情况请用精确路径。
- 浮点数用精确相等比较（`0.1 + 0.2 != 0.3` 那种坑同样存在）；`NaN` 视为相等。
- 数字 `30` 与 `30.0` 视为相等（int/float 互通），但 `true` 与 `1` 会报类型变化。

## License

MIT，见 [LICENSE](LICENSE)。
