#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""jsondiff —— 语义化对比两个 JSON 文档，输出人类可读的结构差异。

纯标准库：json / argparse / sys / difflib / fnmatch / math。

    $ python -m jsondiff before.json after.json
    ~ users[id=7].age: 30 -> 31
    + users[id=10]: {"age":28,"email":"qiang@example.com","id":10,"name":"阿强"}
    - config.debug: true
    ! config.timeout: type int -> string
"""

import argparse
import difflib
import fnmatch
import json
import math
import sys

VERSION = "0.1.0"

# 变更操作符
CHANGED = "~"        # 值变了
ADDED = "+"          # 新增了
REMOVED = "-"        # 删除了
TYPE_CHANGED = "!"   # 类型变了

# 对象数组按 key 匹配时的默认候选字段（按优先级）
DEFAULT_KEYS = ["id", "name", "email"]


def fmt(v, limit=200):
    """把值压成一行 JSON，超长截断。"""
    s = json.dumps(v, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    if len(s) > limit:
        s = s[: limit - 1] + "…"
    return s


def type_name(v):
    if v is None:
        return "null"
    if isinstance(v, bool):
        return "bool"
    if isinstance(v, int):
        return "int"
    if isinstance(v, float):
        return "float"
    if isinstance(v, str):
        return "string"
    if isinstance(v, list):
        return "array"
    if isinstance(v, dict):
        return "object"
    return type(v).__name__


def is_num(v):
    return isinstance(v, (int, float)) and not isinstance(v, bool)


def values_equal(a, b):
    """标量判等：数字 int/float 互通；NaN 视为相等。"""
    if is_num(a) and is_num(b):
        if isinstance(a, float) and isinstance(b, float):
            if math.isnan(a) and math.isnan(b):
                return True
        return a == b
    return a == b


def fingerprint(v):
    return json.dumps(v, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def join(path, key):
    key = str(key)
    return f"{path}.{key}" if path else key


def seg(path, key, val):
    return f"{path}[{key}={fmt(val)}]" if path else f"[{key}={fmt(val)}]"


def pick_key(a, b, by_key):
    """为对象数组挑选匹配字段：要求该字段在两边所有元素都存在且值唯一。"""
    candidates = [by_key] if by_key else list(DEFAULT_KEYS)
    for k in candidates:
        if not k or not a or not b:
            continue
        if not all(isinstance(x, dict) and k in x for x in a):
            continue
        if not all(isinstance(x, dict) and k in x for x in b):
            continue
        fa = [fingerprint(x[k]) for x in a]
        fb = [fingerprint(x[k]) for x in b]
        if len(set(fa)) == len(fa) and len(set(fb)) == len(fb):
            return k
    return None


def diff(a, b, path, by_key, out):
    """递归对比，把 (op, path, old, new) 追加到 out。"""
    if isinstance(a, dict) and isinstance(b, dict):
        for k in a:
            if k not in b:
                out.append((REMOVED, join(path, k), a[k], None))
        for k in b:
            p = join(path, k)
            if k not in a:
                out.append((ADDED, p, None, b[k]))
            else:
                diff(a[k], b[k], p, by_key, out)
        return
    if isinstance(a, list) and isinstance(b, list):
        diff_list(a, b, path, by_key, out)
        return
    p = path or "(root)"
    if isinstance(a, (dict, list)) or isinstance(b, (dict, list)):
        out.append((TYPE_CHANGED, p, a, b))
        return
    if type(a) is not type(b) and not (is_num(a) and is_num(b)):
        out.append((TYPE_CHANGED, p, a, b))
        return
    if not values_equal(a, b):
        out.append((CHANGED, p, a, b))


def diff_list(a, b, path, by_key, out):
    key = pick_key(a, b, by_key)
    if key is None:
        # 没有稳定的 key：按下标逐个对比
        n = min(len(a), len(b))
        for i in range(n):
            diff(a[i], b[i], f"{path}[{i}]", by_key, out)
        for i in range(n, len(a)):
            out.append((REMOVED, f"{path}[{i}]", a[i], None))
        for i in range(n, len(b)):
            out.append((ADDED, f"{path}[{i}]", b[i], None))
        return
    ma = {fingerprint(x[key]): x for x in a}
    mb = {fingerprint(x[key]): x for x in b}
    for fpr, x in ma.items():
        p = seg(path, key, x[key])
        if fpr not in mb:
            out.append((REMOVED, p, x, None))
    for fpr, x in mb.items():
        p = seg(path, key, x[key])
        if fpr not in ma:
            out.append((ADDED, p, None, x))
        else:
            diff(ma[fpr], x, p, by_key, out)


def render_text(changes, compact):
    lines = []
    for op, p, old, new in changes:
        if compact:
            lines.append(f"{op} {p}")
            continue
        if op == TYPE_CHANGED:
            lines.append(f"{op} {p}: type {type_name(old)} -> {type_name(new)}")
        elif (
            op == CHANGED
            and isinstance(old, str)
            and isinstance(new, str)
            and ("\n" in old or "\n" in new)
        ):
            # 多行文本：用 unified diff 展示
            lines.append(f"{op} {p}:")
            for ln in difflib.unified_diff(
                old.splitlines(), new.splitlines(), lineterm=""
            ):
                lines.append("    " + ln)
        elif op == CHANGED:
            lines.append(f"{op} {p}: {fmt(old)} -> {fmt(new)}")
        elif op == ADDED:
            lines.append(f"{op} {p}: {fmt(new)}")
        elif op == REMOVED:
            lines.append(f"{op} {p}: {fmt(old)}")
    return "\n".join(lines)


def render_json(changes):
    return json.dumps(
        [{"op": op, "path": p, "old": old, "new": new} for op, p, old, new in changes],
        ensure_ascii=False,
        indent=2,
    )


def load_json(path):
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        sys.stderr.write(f"error: 找不到文件：{path}\n")
        sys.exit(2)
    except json.JSONDecodeError as e:
        sys.stderr.write(f"error: 文件不是合法 JSON：{path}（{e}）\n")
        sys.exit(2)
    except OSError as e:
        sys.stderr.write(f"error: 读取文件失败：{path}（{e}）\n")
        sys.exit(2)


def main(argv=None):
    ap = argparse.ArgumentParser(
        prog="jsondiff",
        description="语义化对比两个 JSON 文件，输出人类可读的结构差异"
        "（~ 变更 / + 新增 / - 删除 / ! 类型变化）。",
    )
    ap.add_argument("before", nargs="?", help="旧 JSON 文件")
    ap.add_argument("after", nargs="?", help="新 JSON 文件")
    ap.add_argument(
        "--by-key",
        default=None,
        metavar="KEY",
        help="对象数组按指定字段匹配（如 --by-key email）；默认依次尝试 id / name / email",
    )
    ap.add_argument(
        "--ignore",
        action="append",
        default=[],
        metavar="PAT",
        help="忽略匹配的路径（fnmatch 语法，如 \"meta.*\"），可重复指定",
    )
    ap.add_argument("--json", action="store_true", help="输出机器可读的 JSON")
    ap.add_argument(
        "--compact", action="store_true", help="紧凑输出：只显示操作符和路径，不显示值"
    )
    ap.add_argument("--version", action="version", version="jsondiff " + VERSION)
    args = ap.parse_args(argv)

    if not args.before or not args.after:
        ap.error("需要指定两个文件：jsondiff before.json after.json")

    a = load_json(args.before)
    b = load_json(args.after)

    changes = []
    diff(a, b, "", args.by_key, changes)
    if args.ignore:
        changes = [
            c
            for c in changes
            if not any(fnmatch.fnmatchcase(c[1], pat) for pat in args.ignore)
        ]
    changes.sort(key=lambda c: c[1])

    if args.json:
        sys.stdout.write(render_json(changes) + "\n")
    elif changes:
        sys.stdout.write(render_text(changes, args.compact) + "\n")
    else:
        sys.stdout.write("无差异。\n")

    return 1 if changes else 0


if __name__ == "__main__":
    sys.exit(main())
