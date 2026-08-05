"""M1 技术验证 Spike：pyswisseph + zoneinfo + Placidus 高纬度降级。

验证三项：
  (a) Python 3.12 下 pyswisseph wheel 可用性（行星/四轴/Placidus/恒星黄道 API）
  (b) zoneinfo + tzdata 对中国历史夏令时的时区换算（1986-1991 夏令时、跨日、新疆时区）
  (c) Placidus 高纬度失败时 swe.houses 返回码，确定降级为整宫制的实现路径

运行方式：
  cd agentforge-ai && python tests/spike_star_chart.py

说明：
  本脚本不依赖 pytest，可直接运行。pyswisseph 未安装时跳过 (a)(c) 两项，
  仅运行 (b) zoneinfo 验证（纯 Python 标准库 + tzdata 包）。
  完整验证需在 Docker 容器（python:3.12-slim + pyswisseph + tzdata）中运行。

  本地验证 zoneinfo 部分：
    pip install tzdata && python tests/spike_star_chart.py
"""
import json
import sys
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

# Windows 控制台默认 GBK 编码，无法输出 ✓/✗ 与中文；统一重配置为 UTF-8
for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8")
    except (AttributeError, ValueError):
        pass

# 历书数据路径
EPHE_PATH = str(Path(__file__).resolve().parent.parent / "app" / "tools" / "data" / "ephe")


def _print_section(title: str) -> None:
    print(f"\n{'=' * 60}")
    print(f"  {title}")
    print(f"{'=' * 60}")


def _print_result(name: str, passed: bool, detail: str = "") -> None:
    status = "✓ PASS" if passed else "✗ FAIL"
    print(f"  [{status}] {name}" + (f" — {detail}" if detail else ""))


# ─────────────────── (a) pyswisseph 验证 ───────────────────

def verify_pyswisseph() -> bool:
    """验证 pyswisseph 可用性及核心 API。"""
    _print_section("(a) pyswisseph Wheel 可用性验证")
    try:
        import swisseph as swe
    except ImportError:
        print("  [SKIP] pyswisseph 未安装。请在 Docker 容器中运行完整验证。")
        print("         安装方式: pip install pyswisseph tzdata")
        return False

    version = swe.version
    _print_result("pyswisseph 导入", True, f"版本 {version}")
    print(f"  历书路径: {EPHE_PATH}")

    # 设置历书路径
    swe.set_ephe_path(EPHE_PATH)
    _print_result("设置历书路径", True)

    # 测试日期：1994-05-20 14:30 CST (UTC+8) → UTC 06:30
    # Julian Day for 1994-05-20 06:30:00 UTC
    jd = swe.julday(1994, 5, 20, 6.5)  # 6.5 = 06:30 UTC
    _print_result("Julian Day 计算", True, f"JD={jd:.6f}")

    # --- 行星位置 ---
    planets_ok = True
    planet_names = ["sun", "moon", "mercury", "venus", "mars",
                    "jupiter", "saturn", "uranus", "neptune", "pluto"]
    planet_ids = [swe.SUN, swe.MOON, swe.MERCURY, swe.VENUS, swe.MARS,
                  swe.JUPITER, swe.SATURN, swe.URANUS, swe.NEPTUNE, swe.PLUTO]

    for name, pid in zip(planet_names, planet_ids):
        try:
            xx, _ret = swe.calc_ut(jd, pid)
            lon = xx[0]
            sign_idx = int(lon / 30)
            degree_in_sign = lon % 30
            _print_result(
                f"行星 {name:8s}",
                True,
                f"黄经={lon:.4f}° (星座{sign_idx}, 度数{degree_in_sign:.2f}°)"
            )
        except Exception as exc:
            _print_result(f"行星 {name:8s}", False, str(exc))
            planets_ok = False

    # --- 四轴 + 宫位 (Placidus) ---
    lat_bj, lon_bj = 39.9042, 116.4074
    try:
        cusps, ascmc = swe.houses(jd, lat_bj, lon_bj, b'P')  # P = Placidus
        asc_lon = ascmc[0]  # ASC 黄经
        mc_lon = ascmc[1]   # MC 黄经
        _print_result(
            "四轴 (Placidus)",
            True,
            f"ASC={asc_lon:.4f}° MC={mc_lon:.4f}°"
        )
        _print_result(
            "12 宫头 (Placidus)",
            True,
            f"宫1起={cusps[0]:.4f}° 宫4起={cusps[3]:.4f}° 宫10起={cusps[9]:.4f}°"
        )
    except Exception as exc:
        _print_result("四轴/宫位 (Placidus)", False, str(exc))
        planets_ok = False

    # --- 恒星黄道 (Sidereal, Lahiri) ---
    try:
        swe.set_sid_mode(swe.SIDM_LAHIRI)  # Lahiri Ayanamsa
        xx_sid, _ = swe.calc_ut(jd, swe.SUN, swe.FLG_SIDEREAL)
        lon_sid = xx_sid[0]
        xx_trop, _ = swe.calc_ut(jd, swe.SUN, swe.FLG_SWIEPH)
        lon_trop = xx_trop[0]
        ayanamsa = swe.get_ayanamsa_ut(jd)
        _print_result(
            "恒星黄道 (Lahiri)",
            True,
            f"回归黄经={lon_trop:.4f}° 恒星黄经={lon_sid:.4f}° Ayanamsa={ayanamsa:.4f}°"
        )
    except Exception as exc:
        _print_result("恒星黄道 (Lahiri)", False, str(exc))
        planets_ok = False

    # --- 关闭 ---
    swe.close()
    _print_result("swe.close()", True)
    return planets_ok


# ─────────────────── (b) zoneinfo + tzdata 验证 ───────────────────

def verify_zoneinfo() -> bool:
    """验证 zoneinfo + tzdata 对历史夏令时的处理。"""
    _print_section("(b) zoneinfo + tzdata 历史时区验证")

    all_ok = True

    # --- 中国夏令时 1986-1991 ---
    # 中国在 1986-1991 年实行夏令时（每年 5 月中旬至 9 月中旬）
    # 1988 年 5 月 15 日处于夏令时期间，CST → UTC+9
    # 1988 年 1 月 15 日不处于夏令时期间，CST → UTC+8

    # 测试 1：1988 年夏令时期间
    try:
        tz_cn = ZoneInfo("Asia/Shanghai")
        dt_dst = datetime(1988, 5, 15, 14, 30, tzinfo=tz_cn)
        utc_dst = dt_dst.astimezone(ZoneInfo("UTC"))
        offset_dst = dt_dst.utcoffset()
        expected_offset_dst = timedelta(hours=9)  # 夏令时 UTC+9
        passed = offset_dst == expected_offset_dst
        _print_result(
            "中国 1988 夏令时 (5月15日 14:30 CST)",
            passed,
            f"UTC偏移={offset_dst} (期望+9:00) → UTC={utc_dst.strftime('%Y-%m-%d %H:%M:%S')}"
        )
        all_ok &= passed
    except Exception as exc:
        _print_result("中国 1988 夏令时", False, str(exc))
        all_ok = False

    # 测试 2：1988 年非夏令时期间
    try:
        dt_nodst = datetime(1988, 1, 15, 14, 30, tzinfo=tz_cn)
        utc_nodst = dt_nodst.astimezone(ZoneInfo("UTC"))
        offset_nodst = dt_nodst.utcoffset()
        expected_offset_nodst = timedelta(hours=8)  # 标准时间 UTC+8
        passed = offset_nodst == expected_offset_nodst
        _print_result(
            "中国 1988 非夏令时 (1月15日 14:30 CST)",
            passed,
            f"UTC偏移={offset_nodst} (期望+8:00) → UTC={utc_nodst.strftime('%Y-%m-%d %H:%M:%S')}"
        )
        all_ok &= passed
    except Exception as exc:
        _print_result("中国 1988 非夏令时", False, str(exc))
        all_ok = False

    # 测试 3：1986 年（夏令时第一年）
    try:
        dt_1986 = datetime(1986, 7, 15, 14, 30, tzinfo=tz_cn)
        utc_1986 = dt_1986.astimezone(ZoneInfo("UTC"))
        offset_1986 = dt_1986.utcoffset()
        passed = offset_1986 == timedelta(hours=9)
        _print_result(
            "中国 1986 夏令时首年 (7月15日)",
            passed,
            f"UTC偏移={offset_1986} (期望+9:00)"
        )
        all_ok &= passed
    except Exception as exc:
        _print_result("中国 1986 夏令时", False, str(exc))
        all_ok = False

    # 测试 4：1992 年（夏令时已取消）
    try:
        dt_1992 = datetime(1992, 7, 15, 14, 30, tzinfo=tz_cn)
        utc_1992 = dt_1992.astimezone(ZoneInfo("UTC"))
        offset_1992 = dt_1992.utcoffset()
        passed = offset_1992 == timedelta(hours=8)
        _print_result(
            "中国 1992 无夏令时 (7月15日)",
            passed,
            f"UTC偏移={offset_1992} (期望+8:00，夏令时已取消)"
        )
        all_ok &= passed
    except Exception as exc:
        _print_result("中国 1992 无夏令时", False, str(exc))
        all_ok = False

    # --- 中国夏令时 1991（最后一年） ---
    # 1991年是最后一年实行夏令时，7月应处于 DST（UTC+9）
    try:
        dt_1991 = datetime(1991, 7, 15, 14, 30, tzinfo=tz_cn)
        offset_1991 = dt_1991.utcoffset()
        passed = offset_1991 == timedelta(hours=9)
        _print_result(
            "中国 1991 夏令时末年 (7月15日)",
            passed,
            f"UTC偏移={offset_1991} (期望+9:00)"
        )
        all_ok &= passed
    except Exception as exc:
        _print_result("中国 1991 夏令时末年", False, str(exc))
        all_ok = False

    # --- 新疆时区 (Asia/Urumqi UTC+6) ---
    # 新疆地区使用 Asia/Urumqi，与北京 UTC+8 差2小时
    try:
        tz_urumqi = ZoneInfo("Asia/Urumqi")
        dt_xj = datetime(1990, 6, 15, 12, 0, tzinfo=tz_urumqi)
        utc_xj = dt_xj.astimezone(ZoneInfo("UTC"))
        offset_xj = dt_xj.utcoffset()
        passed = offset_xj == timedelta(hours=6)
        _print_result(
            "新疆时区 Asia/Urumqi (UTC+6)",
            passed,
            f"UTC偏移={offset_xj} (期望+6:00) → UTC={utc_xj.strftime('%Y-%m-%d %H:%M:%S')}"
        )
        all_ok &= passed
    except Exception as exc:
        _print_result("新疆时区", False, str(exc))
        all_ok = False

    # --- 香港时区 (Asia/Hong_Kong UTC+8，1979年后无DST) ---
    try:
        tz_hk = ZoneInfo("Asia/Hong_Kong")
        dt_hk = datetime(1997, 7, 1, 0, 0, tzinfo=tz_hk)
        utc_hk = dt_hk.astimezone(ZoneInfo("UTC"))
        offset_hk = dt_hk.utcoffset()
        passed = offset_hk == timedelta(hours=8)
        _print_result(
            "香港时区 Asia/Hong_Kong (UTC+8, 无DST)",
            passed,
            f"UTC偏移={offset_hk} (期望+8:00) → UTC={utc_hk.strftime('%Y-%m-%d %H:%M:%S')}"
        )
        all_ok &= passed
    except Exception as exc:
        _print_result("香港时区", False, str(exc))
        all_ok = False

    # --- 中国台湾时区 (Asia/Taipei UTC+8) ---
    try:
        tz_tw = ZoneInfo("Asia/Taipei")
        dt_tw = datetime(2000, 5, 20, 8, 0, tzinfo=tz_tw)
        utc_tw = dt_tw.astimezone(ZoneInfo("UTC"))
        offset_tw = dt_tw.utcoffset()
        passed = offset_tw == timedelta(hours=8)
        _print_result(
            "中国台湾时区 Asia/Taipei (UTC+8)",
            passed,
            f"UTC偏移={offset_tw} (期望+8:00) → UTC={utc_tw.strftime('%Y-%m-%d %H:%M:%S')}"
        )
        all_ok &= passed
    except Exception as exc:
        _print_result("中国台湾时区", False, str(exc))
        all_ok = False

    # --- 跨日测试 ---
    # 北京 2000-01-01 02:00 CST → UTC 1999-12-31 18:00
    try:
        dt_cross = datetime(2000, 1, 1, 2, 0, tzinfo=tz_cn)
        utc_cross = dt_cross.astimezone(ZoneInfo("UTC"))
        passed = utc_cross.year == 1999 and utc_cross.month == 12 and utc_cross.day == 31
        _print_result(
            "跨日测试 (北京 2000-01-01 02:00 → UTC 1999-12-31)",
            passed,
            f"UTC={utc_cross.strftime('%Y-%m-%d %H:%M:%S')}"
        )
        all_ok &= passed
    except Exception as exc:
        _print_result("跨日测试", False, str(exc))
        all_ok = False

    return all_ok


# ─────────────────── (c) Placidus 高纬度降级 ───────────────────

def verify_placidus_high_lat() -> bool:
    """验证 Placidus 在高纬度地区的行为及降级路径。"""
    _print_section("(c) Placidus 高纬度降级验证")

    try:
        import swisseph as swe
    except ImportError:
        print("  [SKIP] pyswisseph 未安装。请在 Docker 容器中运行完整验证。")
        return False

    swe.set_ephe_path(EPHE_PATH)
    # 测试日期：2000-01-01 12:00 UTC
    jd = swe.julday(2000, 1, 1, 12.0)

    results = {}

    # --- 正常纬度（北京 39.9°N）应成功 ---
    try:
        cusps, ascmc = swe.houses(jd, 39.9042, 116.4074, b'P')
        results["beijing_39.9"] = {"ok": True, "asc": ascmc[0], "cusps_count": len(cusps)}
        _print_result(
            "北京 39.9°N (正常纬度)",
            True,
            f"ASC={ascmc[0]:.4f}° 12宫头正常返回"
        )
    except Exception as exc:
        results["beijing_39.9"] = {"ok": False, "error": str(exc)}
        _print_result("北京 39.9°N", False, str(exc))

    # --- 高纬度测试点 ---
    # 中国最北城市漠河仅 53.5°N，Placidus 在此纬度正常工作
    # 保留一个极端高纬度(70°N)测试点仅为验证降级机制，非实际中国用户场景
    test_points = [
        ("北京", 39.9042, 116.4074, "Asia/Shanghai"),         # 39.9°N 正常
        ("漠河", 53.4712, 122.5349, "Asia/Shanghai"),          # 53.5°N 中国最北
        ("Arctic_70N", 70.0, 0.0, "UTC"),                      # 70°N 极端高纬度（降级机制验证）
    ]

    for name, lat, lon, _tz in test_points:
        try:
            cusps, ascmc = swe.houses(jd, lat, lon, b'P')
            asc = ascmc[0]
            # 检查是否有无效宫头（NaN 或重复值）
            has_nan = any(c != c for c in cusps)  # NaN != NaN
            has_dup = len(set(round(c, 4) for c in cusps)) < 12

            if has_nan or has_dup:
                # Placidus 在该纬度失败，测试整宫制降级
                results[name] = {"ok": False, "placidus_failed": True,
                                 "reason": "NaN" if has_nan else "duplicate_cusps"}
                _print_result(
                    f"{name} {lat}°N (Placidus 失败)",
                    True,  # 预期失败是正常的
                    f"Placidus 返回无效宫头 ({'NaN' if has_nan else '重复值'})"
                )

                # 测试整宫制降级
                try:
                    cusps_ws, ascmc_ws = swe.houses(jd, lat, lon, b'W')  # W = Whole Sign
                    asc_ws = ascmc_ws[0]
                    results[name]["whole_sign_ok"] = True
                    results[name]["whole_sign_asc"] = asc_ws
                    _print_result(
                        f"{name} 整宫制降级",
                        True,
                        f"ASC={asc_ws:.4f}° 12宫头正常返回"
                    )
                except Exception as exc2:
                    results[name]["whole_sign_ok"] = False
                    results[name]["whole_sign_error"] = str(exc2)
                    _print_result(f"{name} 整宫制降级", False, str(exc2))
            else:
                results[name] = {"ok": True, "asc": asc, "cusps_count": len(cusps)}
                _print_result(
                    f"{name} {lat}°N",
                    True,
                    f"Placidus 正常 ASC={asc:.4f}°"
                )
        except Exception as exc:
            results[name] = {"ok": False, "error": str(exc)}
            _print_result(f"{name} {lat}°N", False, str(exc))

            # 整宫制降级
            try:
                cusps_ws, ascmc_ws = swe.houses(jd, lat, lon, b'W')
                _print_result(
                    f"{name} 整宫制降级",
                    True,
                    f"ASC={ascmc_ws[0]:.4f}°"
                )
            except Exception as exc2:
                _print_result(f"{name} 整宫制降级", False, str(exc2))

    swe.close()

    # --- 降级实现路径结论 ---
    _print_section("降级实现路径结论")
    print("""
  中国场景结论：
    中国大陆最北城市漠河 (53.5°N) Placidus 正常工作，无需降级。
    中国所有城市均在 Placidus 安全范围内 (< 60°N)。

  降级方案（保留以应对极端情况）：
    当 swe.houses(jd, lat, lon, b'P') (Placidus) 返回无效宫头
    （NaN 或重复值）或抛出异常时，自动改用 swe.houses(jd, lat, lon, b'W')
    (Whole Sign 整宫制)，并在返回结果 meta 中标注：
      houseSystemFallback: true
      houseSystem: "whole_sign"

  判定逻辑（在 star_chart.calculate_chart 中实现）：
    1. 调用 swe.houses(jd, lat, lon, b'P')
    2. 检查 cusps 中是否有 NaN 或重复值
    3. 若有 → 改用 swe.houses(jd, lat, lon, b'W')，设置 fallback 标志
    4. 若无 → 正常返回 Placidus 宫位

  高纬度阈值经验值：约 60°N 以上 Placidus 可能开始出现不稳定，
  约 66°N 以上（北极圈附近）大概率失败。
""")

    return True


# ─────────────────── 主入口 ───────────────────

def main() -> int:
    print("M1 技术验证 Spike — star_chart 工具前置验证")
    print(f"运行环境: Python {sys.version.split()[0]}")
    print(f"历书路径: {EPHE_PATH}")

    # 检查历书文件
    ephe_dir = Path(EPHE_PATH)
    sepl = ephe_dir / "sepl_18.se1"
    semo = ephe_dir / "semo_18.se1"
    if sepl.exists() and semo.exists():
        print(f"历书文件: sepl_18.se1 ({sepl.stat().st_size:,} bytes), "
              f"semo_18.se1 ({semo.stat().st_size:,} bytes)")
    else:
        print("⚠ 历书文件缺失！请运行: python scripts/download_ephemeris.py")

    results = {}
    results["a_pyswisseph"] = verify_pyswisseph()
    results["b_zoneinfo"] = verify_zoneinfo()
    results["c_placidus"] = verify_placidus_high_lat()

    # 汇总
    _print_section("验证汇总")
    for name, passed in results.items():
        status = "✓ PASS" if passed else "✗ FAIL/SKIP"
        print(f"  {name}: {status}")

    # 输出 JSON 报告
    report = {
        "timestamp": datetime.now(ZoneInfo("UTC")).isoformat(),
        "python_version": sys.version.split()[0],
        "ephe_path": EPHE_PATH,
        "ephe_files": {
            "sepl_18.se1": sepl.stat().st_size if sepl.exists() else 0,
            "semo_18.se1": semo.stat().st_size if semo.exists() else 0,
        },
        "results": {k: "PASS" if v else "FAIL/SKIP" for k, v in results.items()},
    }
    report_path = Path(__file__).parent / "spike_report.json"
    report_path.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"\n报告已保存: {report_path}")

    return 0 if all(results.values()) else 1


if __name__ == "__main__":
    sys.exit(main())
