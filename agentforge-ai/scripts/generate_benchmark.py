#!/usr/bin/env python3
"""生成验收基准用例：使用 pyswisseph 计算 10 组出生数据的期望值。

口径：Tropical + Geocentric + Placidus
覆盖：正常案例 + 中国夏令时(1986-1991各阶段) + 跨日 + 新疆时区 + 港澳台 + 高纬度(漠河)

运行方式：
  cd agentforge-ai && python scripts/generate_benchmark.py

输出：tests/fixtures/benchmark_cases.json
"""
import json
import sys
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

# 历书路径
EPHE_PATH = str(Path(__file__).resolve().parent.parent / "app" / "tools" / "data" / "ephe")
FIXTURES_DIR = Path(__file__).resolve().parent.parent / "tests" / "fixtures"

# 十大星体
PLANETS = [
    ("sun", 0), ("moon", 1), ("mercury", 2), ("venus", 3), ("mars", 4),
    ("jupiter", 5), ("saturn", 6), ("uranus", 7), ("neptune", 8), ("pluto", 9),
]

# 黄道十二宫中文名
SIGNS_ZH = [
    "白羊座", "金牛座", "双子座", "巨蟹座", "狮子座", "处女座",
    "天秤座", "天蝎座", "射手座", "摩羯座", "水瓶座", "双鱼座",
]


def _local_to_utc(local_dt: datetime) -> datetime:
    """将带时区的本地时间转为 UTC。"""
    return local_dt.astimezone(ZoneInfo("UTC"))


def _jd_from_utc(utc_dt: datetime) -> float:
    """UTC datetime → Julian Day。"""
    import swisseph as swe
    return swe.julday(
        utc_dt.year, utc_dt.month, utc_dt.day,
        utc_dt.hour + utc_dt.minute / 60.0 + utc_dt.second / 3600.0
    )


def calculate_expected(birth_date: str, birth_time: str, lat: float, lng: float,
                       timezone: str, label: str, notes: str = "") -> dict:
    """计算一组出生数据的期望值。"""
    import swisseph as swe
    swe.set_ephe_path(EPHE_PATH)

    # 解析出生时间
    h, m = map(int, birth_time.split(":"))
    local_dt = datetime(
        int(birth_date[:4]), int(birth_date[5:7]), int(birth_date[8:10]),
        h, m, tzinfo=ZoneInfo(timezone)
    )
    utc_dt = _local_to_utc(local_dt)
    jd = _jd_from_utc(utc_dt)

    # 行星黄经
    planets = {}
    for name, pid in PLANETS:
        xx, _ret = swe.calc_ut(jd, pid)
        lon = xx[0]
        sign_idx = int(lon / 30)
        planets[name] = {
            "longitude": round(lon, 4),
            "sign": SIGNS_ZH[sign_idx],
            "signIndex": sign_idx,
            "degree": round(lon % 30, 4),
        }

    # 四轴 + 宫位 (Placidus)
    try:
        cusps, ascmc = swe.houses(jd, lat, lng, b'P')
        house_system = "placidus"
        fallback = False
    except Exception:
        cusps, ascmc = swe.houses(jd, lat, lng, b'W')
        house_system = "whole_sign"
        fallback = True

    asc_lon = ascmc[0]
    mc_lon = ascmc[1]
    desc_lon = (asc_lon + 180) % 360
    ic_lon = (mc_lon + 180) % 360

    # 宫位表
    houses = {}
    for i in range(12):
        cusp = cusps[i]
        sign_idx = int(cusp / 30)
        houses[str(i + 1)] = {
            "cusp": round(cusp, 4),
            "sign": SIGNS_ZH[sign_idx],
        }

    swe.close()

    return {
        "label": label,
        "notes": notes,
        "birthDate": birth_date,
        "birthTime": birth_time,
        "latitude": lat,
        "longitude": lng,
        "timezone": timezone,
        "localDateTime": local_dt.isoformat(),
        "utDateTime": utc_dt.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "julianDay": round(jd, 6),
        "expected": {
            "meta": {
                "zodiac": "tropical",
                "houseSystem": house_system,
                "houseSystemFallback": fallback,
                "ephemeris": "pyswisseph",
            },
            "ascendant": {
                "longitude": round(asc_lon, 4),
                "sign": SIGNS_ZH[int(asc_lon / 30)],
                "degree": round(asc_lon % 30, 4),
            },
            "midheaven": {
                "longitude": round(mc_lon, 4),
                "sign": SIGNS_ZH[int(mc_lon / 30)],
                "degree": round(mc_lon % 30, 4),
            },
            "descendant": {
                "longitude": round(desc_lon, 4),
                "sign": SIGNS_ZH[int(desc_lon / 30)],
                "degree": round(desc_lon % 30, 4),
            },
            "imumCoeli": {
                "longitude": round(ic_lon, 4),
                "sign": SIGNS_ZH[int(ic_lon / 30)],
                "degree": round(ic_lon % 30, 4),
            },
            "planets": planets,
            "houses": houses,
        },
    }


# ─────────────────── 测试用例定义 ───────────────────

TEST_CASES = [
    {
        "label": "case_01_normal_beijing",
        "birthDate": "1994-05-20",
        "birthTime": "14:30",
        "lat": 39.9042,
        "lng": 116.4074,
        "timezone": "Asia/Shanghai",
        "notes": "正常案例：北京，无夏令时（1994年中国已取消夏令时）",
    },
    {
        "label": "case_02_china_dst_1988",
        "birthDate": "1988-07-15",
        "birthTime": "10:00",
        "lat": 31.2304,
        "lng": 121.4737,
        "timezone": "Asia/Shanghai",
        "notes": "中国夏令时：1988年7月15日，UTC+9（夏令时），验证时区换算",
    },
    {
        "label": "case_03_china_dst_1986_first_year",
        "birthDate": "1986-05-10",
        "birthTime": "08:00",
        "lat": 39.9042,
        "lng": 116.4074,
        "timezone": "Asia/Shanghai",
        "notes": "中国夏令时首年：1986年5月（夏令时刚开始），UTC+9",
    },
    {
        "label": "case_04_china_dst_1991_last_year",
        "birthDate": "1991-07-15",
        "birthTime": "10:00",
        "lat": 23.1291,
        "lng": 113.2644,
        "timezone": "Asia/Shanghai",
        "notes": "中国夏令时末年：1991年7月15日，UTC+9（1991年是最后一年实行夏令时）",
    },
    {
        "label": "case_05_post_dst_summer",
        "birthDate": "1995-07-20",
        "birthTime": "14:00",
        "lat": 30.5728,
        "lng": 104.0668,
        "timezone": "Asia/Shanghai",
        "notes": "无夏令时夏季：1995年7月，成都，UTC+8（1992年起取消夏令时）",
    },
    {
        "label": "case_06_cross_day_midnight",
        "birthDate": "2000-01-01",
        "birthTime": "02:00",
        "lat": 39.9042,
        "lng": 116.4074,
        "timezone": "Asia/Shanghai",
        "notes": "跨日案例：北京 2000-01-01 02:00 CST → UTC 1999-12-31 18:00，UTC日期与本地日期不同",
    },
    {
        "label": "case_07_xinjiang_urumqi",
        "birthDate": "1990-06-15",
        "birthTime": "12:00",
        "lat": 43.8256,
        "lng": 87.6168,
        "timezone": "Asia/Urumqi",
        "notes": "新疆时区：乌鲁木齐，Asia/Urumqi UTC+6（与北京 UTC+8 差2小时）",
    },
    {
        "label": "case_08_hong_kong",
        "birthDate": "1997-07-01",
        "birthTime": "00:00",
        "lat": 22.3193,
        "lng": 114.1694,
        "timezone": "Asia/Hong_Kong",
        "notes": "香港回归日：1997年7月1日 00:00，Asia/Hong_Kong UTC+8（香港1979年后无DST）",
    },
    {
        "label": "case_09_taipei",
        "birthDate": "2000-05-20",
        "birthTime": "08:00",
        "lat": 25.0330,
        "lng": 121.5654,
        "timezone": "Asia/Taipei",
        "notes": "中国台湾：台北，Asia/Taipei UTC+8（台湾1980年后无DST）",
    },
    {
        "label": "case_10_mohe_high_lat",
        "birthDate": "1995-06-15",
        "birthTime": "12:00",
        "lat": 53.4712,
        "lng": 122.5349,
        "timezone": "Asia/Shanghai",
        "notes": "高纬度：漠河 53.5°N（中国最北城市），测试 Placidus 在中国最高纬度的稳定性",
    },
]


def main() -> int:
    try:
        import swisseph as swe
    except ImportError:
        print("错误：pyswisseph 未安装。请在 Docker 容器中运行：")
        print("  cd agentforge-ai && pip install pyswisseph tzdata && python scripts/generate_benchmark.py")
        return 1

    FIXTURES_DIR.mkdir(parents=True, exist_ok=True)

    cases = []
    for tc in TEST_CASES:
        print(f"  计算 {tc['label']}...", end=" ", flush=True)
        try:
            result = calculate_expected(
                tc["birthDate"], tc["birthTime"],
                tc["lat"], tc["lng"], tc["timezone"],
                tc["label"], tc["notes"]
            )
            cases.append(result)
            print(f"OK (JD={result['julianDay']:.4f}, ASC={result['expected']['ascendant']['sign']})")
        except Exception as exc:
            print(f"FAILED: {exc}")
            return 1

    output = {
        "description": "star_chart 验收基准用例 — Tropical + Geocentric + Placidus（中国时区场景）",
        "generatedBy": "scripts/generate_benchmark.py (pyswisseph)",
        "tolerance": 0.5,
        "toleranceUnit": "degree",
        "caseCount": len(cases),
        "cases": cases,
    }

    output_path = FIXTURES_DIR / "benchmark_cases.json"
    output_path.write_text(
        json.dumps(output, indent=2, ensure_ascii=False),
        encoding="utf-8"
    )
    print(f"\n完成！{len(cases)} 条用例已保存到 {output_path}")
    print(f"验收标准：关键点位误差 < {output['tolerance']}°")
    return 0


if __name__ == "__main__":
    sys.exit(main())
