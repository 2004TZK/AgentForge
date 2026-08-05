"""M2.6 并发检查：pyswisseph 的 set_sid_mode 为进程级全局状态。

验证目标：tropical / sidereal 并发请求下不互相污染，结果稳定。
策略：N 个线程并发调用 calculate_chart，一半 tropical 一半 sidereal，
每个线程循环多次，核对每次结果的 zodiac 与经度是否与该线程期望口径一致。

若 set_sid_mode 全局状态被并发污染，会出现 zodiac 标注与经度口径不匹配、
或同一线程不同轮次结果漂移。

运行：.tmp/py311/python.exe tests/spike_star_chart_concurrency.py
"""
import sys
import threading
import traceback
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.tools.star_chart import calculate_chart  # noqa: E402

BASE = {"birth_date": "1994-05-20", "birth_time": "14:30", "city": "北京"}
N_THREADS = 8
ROUNDS = 5


def worker(tid: int, results: list, errors: list):
    zodiac = "sidereal" if tid % 2 == 0 else "tropical"
    try:
        for _ in range(ROUNDS):
            chart = calculate_chart(**BASE, zodiac=zodiac)
            meta = chart["meta"]
            sun = chart["planets"]["sun"]
            # 核对 1：meta 口径与本线程一致
            if meta["zodiac"] != zodiac:
                results.append(("口径污染", tid, zodiac, meta["zodiac"], sun["longitude"]))
                return
            # 核对 2：同一线程同一口径下经度必须完全一致（确定性计算）
            results.append(("ok", tid, zodiac, sun["longitude"]))
    except Exception as exc:  # noqa: BLE001
        errors.append((tid, repr(exc), traceback.format_exc()))


def main() -> int:
    threads = []
    results: list = []
    errors: list = []
    for tid in range(N_THREADS):
        t = threading.Thread(target=worker, args=(tid, results, errors))
        threads.append(t)
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    ok_rows = [r for r in results if r[0] == "ok"]
    bad_rows = [r for r in results if r[0] != "ok"]

    # 汇总：每个线程每一轮的结果
    per_thread = {}
    for _kind, tid, zodiac, lon in ok_rows:
        per_thread.setdefault(tid, []).append((zodiac, lon))
    print(f"线程数={N_THREADS} 轮次={ROUNDS} 成功={len(ok_rows)} 异常={len(errors)} 污染={len(bad_rows)}")

    drifted = []
    for tid, rows in sorted(per_thread.items()):
        lons = {r[1] for r in rows}
        if len(lons) != 1:
            drifted.append((tid, lons))
        print(f"  tid={tid} zodiac={rows[0][0]} rounds={len(rows)} 经度唯一值={len(lons)}")

    if errors:
        print("== 异常 ==")
        for tid, exc, tb in errors[:3]:
            print(f"tid={tid} {exc}")
            print(tb[-500:])
    if bad_rows:
        print("== 口径污染 ==")
        for row in bad_rows:
            print(row)

    if errors or bad_rows or drifted:
        print("结论：❌ 存在并发污染或异常")
        return 1
    print("结论：✅ 并发下 tropical/sidereal 口径稳定，无污染（线程内结果完全确定）")
    return 0


if __name__ == "__main__":
    sys.exit(main())
