# -*- coding: utf-8 -*-
"""星盘知识库五件套切片脚本（M3.2.1 方式 A：零代码预拆）。

按计划粒度将 docs/ 下五件套拆为小块 .md，供逐块上传 RAG 入库：
- 星盘完整阅读逻辑手册.md    → 按 `##` 章节
- 星盘宫位完整解析.md        → 按 `## 第N宫`
- 行星落座速查表.md          → 按 `##` 行星/主题节
- 行星守护星座表.md          → 按 `##` 章节 + `###` 行星
- 格局速查表.md              → 按 `##` 格局（`#` 分部导言并入首块）

原文件保留；输出到 docs/star-chart-kb/，文件名 {文档名}-{块标题}.md。
切片边界取标题行，天然不切碎表格行。可重复执行（重跑覆盖输出目录）。
"""
from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "docs"
OUT = ROOT / "docs" / "star-chart-kb"

# 文件名非法字符（Windows/通用）：\/:*?"<>| 与换行
ILLEGAL = re.compile(r'[\\/:*?"<>|\r\n]')

def clean_name(title: str) -> str:
    """标题 → 文件名字段：去副标题（—— 后）与序号前缀外杂项，替换 / 为 -。"""
    title = re.split(r"[—–—–]{2,}|\s+——?\s+", title)[0].strip()
    name = ILLEGAL.sub("-", title).strip()
    name = re.sub(r"\s+", " ", name)
    return name

def split_by_heading(text: str, level: str) -> list[tuple[str, list[str]]]:
    """按指定级别标题切分：返回 [(标题, 块内容)]，文件头（# 标题+引言）并入首块。"""
    lines = text.splitlines(keepends=True)
    blocks: list[tuple[str, list[str]]] = []
    head: list[str] = []
    title = None
    body: list[str] = []
    for ln in lines:
        m = re.match(rf"^{level}\s+(.+?)\s*$", ln.rstrip("\n"))
        if m:
            if title is not None:
                blocks.append((title, body))
            title = m.group(1)
            body = list(head) + [ln]  # 文件头并入首块
            head = []
        elif title is None:
            head.append(ln)
        else:
            body.append(ln)
    if title is not None:
        blocks.append((title, body))
    return blocks

def split_guardian_table(text: str) -> list[tuple[str, list[str]]]:
    """行星守护星座表两级切分：先按 ## 章节，'三、逐星详解' 块再按 ### 行星拆开。"""
    blocks = split_by_heading(text, "##")
    result: list[tuple[str, list[str]]] = []
    for t, b in blocks:
        sub = split_by_heading("".join(b), "###")
        if len(sub) > 1 or (sub and sub[0][0] != t):
            result.extend(sub)
        else:
            result.append((t, b))
    return result

def write_block(doc: str, title: str, body: list[str]) -> Path:
    name = f"{doc}-{clean_name(title)}.md"
    out = OUT / name
    out.write_text("".join(body), encoding="utf-8")
    return out

def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    total = 0
    for fname, level in [
        ("星盘完整阅读逻辑手册.md", "##"),
        ("星盘宫位完整解析.md", "##"),
        ("行星落座速查表.md", "##"),
        ("行星守护星座表.md", "##"),
        ("格局速查表.md", "##"),
    ]:
        text = (SRC / fname).read_text(encoding="utf-8")
        blocks = (
            split_guardian_table(text)
            if fname == "行星守护星座表.md"
            else split_by_heading(text, level)
        )
        print(f"== {fname} → {len(blocks)} 块")
        for title, body in blocks:
            p = write_block(fname[:-3], title, body)
            chars = len("".join(body))
            print(f"  {p.name:52s} {len(body):4d} 行  {chars:5d} 字符")
            total += 1
    print(f"\n共 {total} 个切片文件 → {OUT}")

if __name__ == "__main__":
    sys.exit(main())
