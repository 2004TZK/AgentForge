#!/usr/bin/env python3
"""下载瑞士星历表数据文件（Swiss Ephemeris se1 格式）。

从 GitHub 官方仓库 (aloistr/swisseph) 下载覆盖 1800-2399 的精简版历书：
- sepl_18.se1: 行星历书（太阳至冥王星），~484KB
- semo_18.se1: 月亮历书，~1.3MB
总计 ~1.8MB

用法：
  python scripts/download_ephemeris.py [--output-dir PATH]

默认输出目录：app/tools/data/ephe/
"""
import argparse
import sys
import urllib.request
from pathlib import Path

# GitHub 官方仓库 raw 文件 URL
BASE_URL = "https://raw.githubusercontent.com/aloistr/swisseph/master/ephe"
FILES = {
    "sepl_18.se1": "行星历书（太阳至冥王星，1800-2399）",
    "semo_18.se1": "月亮历书（1800-2399）",
}


def download(url: str, dest: Path) -> int:
    """下载文件，返回字节数。"""
    with urllib.request.urlopen(url) as resp:
        data = resp.read()
    dest.write_bytes(data)
    return len(data)


def main() -> int:
    parser = argparse.ArgumentParser(description="下载瑞士星历表数据文件")
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path(__file__).resolve().parent.parent / "app" / "tools" / "data" / "ephe",
        help="输出目录（默认: app/tools/data/ephe/）",
    )
    args = parser.parse_args()

    args.output_dir.mkdir(parents=True, exist_ok=True)

    print(f"输出目录: {args.output_dir}")
    total = 0
    for filename, desc in FILES.items():
        url = f"{BASE_URL}/{filename}"
        dest = args.output_dir / filename
        print(f"  下载 {filename} ({desc})...", end=" ", flush=True)
        try:
            size = download(url, dest)
            total += size
            print(f"OK ({size:,} bytes)")
        except Exception as exc:
            print(f"FAILED: {exc}")
            return 1

    # 复制版权声明（如果不存在）
    copyright_file = args.output_dir / "COPYRIGHT.txt"
    if not copyright_file.exists():
        print(f"  提示: 请确保 {copyright_file.name} 版权声明文件存在")

    print(f"\n完成！总计 {total:,} bytes ({total / 1024 / 1024:.1f} MB)")
    print(f"文件覆盖范围: 1800-2399 年")
    return 0


if __name__ == "__main__":
    sys.exit(main())
