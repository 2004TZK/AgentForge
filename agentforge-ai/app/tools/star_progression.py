"""Progression Chart Tool：推运（Progressions）——次限推运（一天=一年）。

V2 扩展（《星盘分析扩展规划》1 节）：
- 输入：本命盘信息（与 star_chart 一致）+ 年龄（岁）或目标日期
- 口径：次限推运（Secondary Progression）——推运儒略日 = 本命儒略日 + 年龄天数
- 输出：推运行星位置（含落本命宫位）+ 推运四轴 + 推运内部相位 + 推运对本命相位

V3 增强：支持次限 / 三限（一天=一月）/ 太阳弧 / 日返 / 月返五种推运。
"""
import json
from datetime import UTC, date, datetime, timedelta

from app.tools.star_base import (
    ANGLES,
    DEFAULT_POINTS,
    EPHE_PATH,
    angle_point,
    aspect_info,
    build_ephemeris,
    compute_aspects,
    house_of_longitude,
    houses_and_angles,
    julday,
    planets_at_jd,
    points_at_jd,
    prepare_chart_inputs,
    validate_date_time,
)
from app.tools.star_chart import calculate_chart

# 1 回归年天数（日历年均值，用于"年龄 → 天数"换算）
DAYS_PER_YEAR = 365.2425

PROGRESSION_TYPES = ("secondary", "tertiary", "solar_arc", "solar_return", "lunar_return")


def _return_jd(
    swe, jd_from: float, target_lon: float, body: int, flags: int, window_days: float
) -> float:
    """二分查找 body 黄经下一次精确回到 target_lon 的儒略日（UT）。"""
    def diff(jd: float) -> float:
        return ((swe.calc_ut(jd, body, flags)[0][0] - target_lon + 180.0) % 360.0) - 180.0

    lo = jd_from
    dlo = diff(lo)
    if dlo > 0:
        # 交点已过 lo：向前步进到 diff <= 0，保证窗口内恰好包含下一次交点
        step = window_days / 200.0
        guard = 0
        while dlo > 0 and guard < 2000:
            lo += step
            dlo = diff(lo)
            guard += 1
    hi = lo + window_days
    for _ in range(80):
        mid = (lo + hi) / 2.0
        if diff(mid) < 0:
            lo = mid
        else:
            hi = mid
    return (lo + hi) / 2.0


def _jd_to_iso(swe, jd: float) -> str:
    """儒略日 → UTC ISO 字符串（用于返照盘展示）。"""
    y, m, d, h = swe.revjul(jd, swe.GREG_CAL)
    hh = int(h)
    mm = round((h - hh) * 60)
    if mm == 60:
        hh += 1
        mm = 0
    return f"{y:04d}-{m:02d}-{d:02d}T{hh:02d}:{mm:02d}:00Z"


def _parse_iso_date(value: str) -> date:
    """解析 YYYY-MM-DD，非法时抛可读 ValueError。"""
    m = value.split("-")
    if len(m) != 3:
        raise ValueError(f"日期格式错误，应为 YYYY-MM-DD：{value}")
    try:
        return date(int(m[0]), int(m[1]), int(m[2]))
    except ValueError as exc:
        raise ValueError(f"日期非法：{value}") from exc


def _age_days(
    birth_date: str,
    age: float | None,
    target_date: str,
) -> tuple[int, str, float | None]:
    """确定推运天数（天）与展示用目标日期/年龄。

    优先级：targetDate（日历天数差）→ age（岁 × 365.2425）→ 今天（UTC）。
    """
    year, month, day, _h, _m = validate_date_time(birth_date, "00:00")
    bd = date(year, month, day)
    if target_date:
        td = _parse_iso_date(target_date)
        days = (td - bd).days
        return days, td.isoformat(), round(days / DAYS_PER_YEAR, 1)
    if age is not None:
        days = round(age * DAYS_PER_YEAR)
        return days, date.fromordinal(bd.toordinal() + days).isoformat(), float(age)
    today = datetime.now(UTC).date()
    days = (today - bd).days
    return days, today.isoformat(), round(days / DAYS_PER_YEAR, 1)


def calculate_progression(
    birth_date: str,
    birth_time: str,
    city: str = "",
    latitude: float | None = None,
    longitude: float | None = None,
    timezone: str = "",
    house_system: str = "placidus",
    zodiac: str = "tropical",
    ayanamsa: str = "lahiri",
    orb_mode: str = "modern",
    aspect_types: list[str] | None = None,
    custom_orbs: dict | None = None,
    points: list[str] | None = None,
    birth_text: str = "",
    age: float | None = None,
    target_date: str = "",
    progression_type: str = "secondary",
    ephemeris_path: str = EPHE_PATH,
) -> dict:
    """推运计算核心函数。

    progression_type:
      - secondary    次限：推运儒略日 = 本命儒略日 + 年龄年数（天）（一天 = 一年）
      - tertiary     三限：一天 = 一月（推运天数 = 年龄天数 × 12 / 365.2425）
      - solar_arc    太阳弧：全盘按次限太阳与本命太阳的差值平移
      - solar_return 日返：太阳回到本命太阳黄经的时刻起盘
      - lunar_return 月返：月亮回到本命月亮黄经的时刻起盘

    Returns:
        推运结果 dict：meta（含年龄/推运日期）+ 本命盘顶层字段 + progressed 区块。
    """
    progression_type = (progression_type or "secondary").lower().replace("-", "_")
    if progression_type not in PROGRESSION_TYPES:
        raise ValueError(
            f"推运类型仅支持 {'、'.join(PROGRESSION_TYPES)}。"
        )
    # 解析出生信息并解析经纬度（推运四轴需要出生地）
    ctx = prepare_chart_inputs(
        birth_date=birth_date,
        birth_time=birth_time,
        city=city,
        latitude=latitude,
        longitude=longitude,
        timezone=timezone,
        house_system=house_system,
        zodiac=zodiac,
        ayanamsa=ayanamsa,
        birth_text=birth_text,
        ephemeris_path=ephemeris_path,
    )
    natal = calculate_chart(
        birth_date=birth_date,
        birth_time=birth_time,
        city=city,
        latitude=latitude,
        longitude=longitude,
        timezone=timezone,
        house_system=house_system,
        zodiac=zodiac,
        ayanamsa=ayanamsa,
        orb_mode=orb_mode,
        aspects=aspect_types,
        custom_orbs=custom_orbs,
        points=points,
        birth_text=birth_text,
        ephemeris_path=ephemeris_path,
    )

    # birthText 场景下 birth_date 可能为空，用解析后的本地时间确定出生日期
    resolved_birth_date = ctx["local_dt"].strftime("%Y-%m-%d")
    days, target_iso, age_value = _age_days(resolved_birth_date, age, target_date)
    swe, flags, _ayanamsa = build_ephemeris(natal["meta"]["zodiac"], ephemeris_path, ayanamsa)
    utc_dt = datetime.fromisoformat(natal["meta"]["utDateTime"])
    jd_natal = julday(swe, utc_dt)
    lat, lon = ctx["lat"], ctx["lon"]
    natal_hs = natal["meta"]["houseSystem"]

    arc_degrees: float | None = None
    return_iso: str | None = None
    display_date = target_iso
    jd_calc: float | None = None
    if progression_type in ("secondary", "tertiary"):
        # 次限：1 天 = 1 年 → 偏移天数 = 年龄（年）= days / 365.2425
        # 三限：1 天 = 1 月 → 偏移天数 = 年龄（月）= days × 12 / 365.2425
        offset = (
            days / DAYS_PER_YEAR
            if progression_type == "secondary"
            else days * 12.0 / DAYS_PER_YEAR
        )
        jd_prog = jd_natal + offset
        jd_calc = jd_prog
        prog_planets = planets_at_jd(swe, jd_prog, flags)
        display_date = (
            date.fromisoformat(resolved_birth_date) + timedelta(days=round(offset))
        ).isoformat()
        _h, prog_angles, prog_hs, prog_fb, _pa_lon, _pmc, _pver = houses_and_angles(
            swe, jd_prog, lat, lon, natal_hs
        )
    elif progression_type == "solar_arc":
        # 先求次限太阳（偏移 = 年龄年数，天），再求全盘平移弧度
        jd_sec = jd_natal + days / DAYS_PER_YEAR
        arc_degrees = (
            planets_at_jd(swe, jd_sec, flags)["sun"]["longitude"]
            - natal["planets"]["sun"]["longitude"]
        ) % 360.0
        prog_planets = {}
        for name, pdata in natal["planets"].items():
            plon = (pdata["longitude"] + arc_degrees) % 360.0
            prog_planets[name] = {
                **angle_point(plon),
                "speed": pdata["speed"],
                "retrograde": pdata["retrograde"],
            }
        prog_angles = {
            k: angle_point((natal[k]["longitude"] + arc_degrees) % 360.0)
            for k in ANGLES
        }
        prog_hs, prog_fb = natal_hs, natal["meta"]["houseSystemFallback"]
    else:
        # 日返 / 月返
        body = swe.SUN if progression_type == "solar_return" else swe.MOON
        natal_lon = natal["planets"]["sun" if progression_type == "solar_return" else "moon"]["longitude"]
        window = 367.0 if progression_type == "solar_return" else 29.0
        jd_ret = _return_jd(swe, jd_natal + days - 1.0, natal_lon, body, flags, window)
        jd_calc = jd_ret
        return_iso = _jd_to_iso(swe, jd_ret)
        display_date = return_iso
        prog_planets = planets_at_jd(swe, jd_ret, flags)
        _h, prog_angles, prog_hs, prog_fb, _pa_lon, _pmc, _pver = houses_and_angles(
            swe, jd_ret, lat, lon, natal_hs
        )

    # 推运虚点（日返/月返按返照时刻；太阳弧按本命 + 弧度）
    if progression_type == "solar_arc":
        prog_points = {}
        for name, pdata in natal.get("points", {}).items():
            plon = (pdata["longitude"] + arc_degrees) % 360.0
            prog_points[name] = {
                **angle_point(plon),
                "speed": pdata.get("speed"),
                "retrograde": pdata.get("retrograde", False),
            }
    else:
        prog_points = points_at_jd(
            swe, jd_calc, flags,
            asc_lon=prog_angles["ascendant"]["longitude"],
            sun_lon=prog_planets["sun"]["longitude"],
            moon_lon=prog_planets["moon"]["longitude"],
            points=points or DEFAULT_POINTS,
        )

    # 推运行星 → 本命宫位（读盘惯例：推运行星放在本命宫位解读）
    natal_house_system = natal_hs
    natal_cusps = [natal["houses"][str(i + 1)]["cusp"] for i in range(12)]
    asc_lon = natal["ascendant"]["longitude"]
    houses: dict[str, dict] = {}
    for i in range(12):
        houses[str(i + 1)] = {"sign": natal["houses"][str(i + 1)]["sign"], "planets": []}
    for pname, pdata in prog_planets.items():
        h = house_of_longitude(natal_cusps, natal_house_system, asc_lon, pdata["longitude"])
        pdata["natalHouse"] = h
        houses[str(h)]["planets"].append(pname)
    for pname, pdata in prog_points.items():
        h = house_of_longitude(natal_cusps, natal_house_system, asc_lon, pdata["longitude"])
        pdata["natalHouse"] = h

    # 推运内部相位
    prog_positions = {
        name: {
            "longitude": p["longitude"],
            "speed": p.get("speed"),
            "orb": None,
        }
        for name, p in prog_planets.items()
    }
    prog_aspects = compute_aspects(
        prog_positions,
        aspect_keys=aspect_types,
        orb_mode=orb_mode,
        custom_orbs=custom_orbs,
    )

    # 推运 → 本命相位
    natal_aspects: list[dict] = []
    for pname, pdata in prog_planets.items():
        for nname, ndata in natal["planets"].items():
            info = aspect_info(
                pdata["longitude"], ndata["longitude"],
                aspect_keys=aspect_types,
                orb_mode=orb_mode,
                speed_a=pdata.get("speed"),
                speed_b=ndata["speed"],
                custom_orbs=custom_orbs,
            )
            if info:
                entry = {
                    "progressed": pname,
                    "natal": nname,
                    "type": info["typeEn"],
                    "angle": info["angle"],
                    "orb": info["orb"],
                }
                if info["direction"]:
                    entry["direction"] = info["direction"]
                natal_aspects.append(entry)

    meta = dict(natal["meta"])
    meta.update({
        "progressionType": progression_type,
        "age": age_value,
        "ageDays": days,
        "targetDate": target_iso,
        "progressedDate": display_date,
        "progressedHouseSystem": prog_hs,
        "progressedHouseSystemFallback": prog_fb,
        "arcDegrees": round(arc_degrees, 4) if arc_degrees is not None else None,
        "returnDate": return_iso,
    })

    return {
        **natal,
        "meta": meta,
        "progressed": {
            "planets": prog_planets,
            "points": prog_points,
            "houses": houses,
            "angles": prog_angles,
            "aspects": prog_aspects,
            "natalAspects": natal_aspects,
            "progressionType": progression_type,
            "arcDegrees": round(arc_degrees, 4) if arc_degrees is not None else None,
            "returnDate": return_iso,
        },
    }


def run(payload: dict, config: dict | None = None) -> str:
    """工具注册表调用入口：返回 JSON 字符串或错误文本。"""
    config = config or {}
    try:
        result = calculate_progression(
            birth_date=payload.get("birthDate", ""),
            birth_time=payload.get("birthTime", ""),
            city=payload.get("city", ""),
            latitude=payload.get("latitude"),
            longitude=payload.get("longitude"),
            timezone=payload.get("timezone", ""),
            house_system=config.get("default_house_system") or payload.get("houseSystem", "") or "placidus",
            zodiac=config.get("default_zodiac") or payload.get("zodiac", "") or "tropical",
            ayanamsa=config.get("default_ayanamsa") or payload.get("ayanamsa", "") or "lahiri",
            orb_mode=config.get("default_orb_mode") or payload.get("orbMode", "") or "modern",
            aspect_types=payload.get("aspects"),
            custom_orbs=payload.get("customOrbs"),
            points=payload.get("points"),
            birth_text=payload.get("birthText", ""),
            age=payload.get("age"),
            target_date=payload.get("targetDate", ""),
            progression_type=payload.get("progressionType", "secondary"),
            ephemeris_path=config.get("ephemeris_path") or EPHE_PATH,
        )
        return json.dumps(result, ensure_ascii=False)
    except ValueError as exc:
        return f"[progression_chart] 错误：{exc}"


SCHEMA = {
    "name": "progression_chart",
    "description": (
        "推运计算工具（V2/V3）。输入本命盘信息与年龄（岁）或目标日期，"
        "输出推运行星位置（含落本命宫位）、推运四轴、推运内部相位与推运对本命相位，"
        "用于'年龄阶段运势'解读。支持次限（一天=一年）/ 三限（一天=一月）/ "
        "太阳弧 / 日返 / 月返。口径与本命盘一致。"
    ),
    "parameters": {
        "birthDate": {
            "type": "string",
            "description": "出生日期（公历），格式 YYYY-MM-DD，如 1994-05-20",
        },
        "birthTime": {
            "type": "string",
            "description": "出生时间（24h 制），格式 HH:MM，如 14:30",
        },
        "city": {
            "type": "string",
            "description": "出生城市名（中文或英文），如 北京 / Beijing。城市在库时自动推断经纬度与时区",
            "required": False,
        },
        "latitude": {
            "type": "number",
            "description": "纬度（-90~90）。城市不在库时使用；与 city 同时提供时以 city 为准",
            "required": False,
        },
        "longitude": {
            "type": "number",
            "description": "经度（-180~180）。城市不在库时使用；与 city 同时提供时以 city 为准",
            "required": False,
        },
        "timezone": {
            "type": "string",
            "description": "出生地 IANA 时区名，如 Asia/Shanghai。使用经纬度输入时必填",
            "required": False,
        },
        "houseSystem": {
            "type": "string",
            "description": "宫位制：placidus（默认）/ whole_sign / equal / koch / regiomontanus / campanus / porphyry / topocentric / alcabitius / morinus",
            "required": False,
        },
        "zodiac": {
            "type": "string",
            "description": "黄道类型：tropical（默认）或 sidereal（恒星黄道）",
            "required": False,
        },
        "ayanamsa": {
            "type": "string",
            "description": "恒星黄道 Ayanamsa（zodiac=sidereal 时生效），默认 lahiri",
            "required": False,
        },
        "orbMode": {
            "type": "string",
            "description": "相位容许度流派：modern（默认）或 classical（按星体）",
            "required": False,
        },
        "aspects": {
            "type": "array",
            "items": {"type": "string"},
            "description": "启用的相位类型（缺省仅五大主相位）",
            "required": False,
        },
        "customOrbs": {
            "type": "object",
            "description": "自定义相位容许度",
            "required": False,
        },
        "points": {
            "type": "array",
            "items": {"type": "string"},
            "description": "推运虚点/小行星（缺省北交点+南交点）",
            "required": False,
        },
        "birthText": {
            "type": "string",
            "description": "本命盘自由文本输入（如 '1994-05-20 14:30 北京'）。提供时优先于结构化字段解析",
            "required": False,
        },
        "age": {
            "type": "number",
            "description": "推运年龄（岁），如 30.5；与 targetDate 二选一，缺省为当前年龄",
            "required": False,
        },
        "targetDate": {
            "type": "string",
            "description": "推运目标日期，格式 YYYY-MM-DD；与 age 二选一（优先于 age）",
            "required": False,
        },
        "progressionType": {
            "type": "string",
            "description": (
                "推运类型：secondary（默认，次限，一天=一年）/ tertiary（三限，一天=一月）/ "
                "solar_arc（太阳弧）/ solar_return（日返）/ lunar_return（月返）"
            ),
            "required": False,
        },
    },
    "config": {
        "ephemeris_path": {
            "type": "string",
            "description": "瑞士星历表数据文件目录路径，默认 app/tools/data/ephe/",
        },
        "default_house_system": {
            "type": "string",
            "description": "默认宫位制：placidus 或 whole_sign",
        },
        "default_zodiac": {
            "type": "string",
            "description": "默认黄道类型：tropical 或 sidereal",
        },
        "default_ayanamsa": {
            "type": "string",
            "description": "默认 Ayanamsa（恒星黄道时生效），默认 lahiri",
        },
        "default_orb_mode": {
            "type": "string",
            "description": "默认容许度流派：modern 或 classical",
        },
    },
}


OUTPUT_SCHEMA_DOC = """
progression_chart 工具出参 JSON 结构定义
========================================

成功时返回 JSON 字符串。顶层字段为本命盘数据（同 star_chart），另含 progressed 区块：

{
  "meta": {
    ...,
    "age": 30.0,                 // 推运年龄（岁）
    "ageDays": 10957,            // 推运天数（一天=一年）
    "targetDate": "2024-05-20",  // 目标日历日期（该年龄对应的现实日期）
    "progressedDate": "1994-06-19",  // 推运历书日期（出生 + 年龄年数天）
    "progressedHouseSystem": "placidus",
    "progressedHouseSystemFallback": false
  },
  "progressed": {
    "planets": {  // 推运行星（含 natalHouse：落本命宫位）
      "sun": { "sign": "双子座", "signIndex": 2, "degree": 10.1,
               "longitude": 70.1, "retrograde": false, "natalHouse": 10 },
      ...
    },
    "houses": {  // 推运行星按本命宫位分布
      "10": { "sign": "双子座", "planets": ["sun", "mercury"] }, ...
    },
    "angles": {  // 推运四轴（出生地，推运时刻）
      "ascendant": { "sign": "天秤座", ... }, ...
    },
    "aspects": [  // 推运内部相位
      { "p1": "sun", "p2": "moon", "type": "trine", "orb": 1.3 }, ...
    ],
    "natalAspects": [  // 推运 → 本命相位
      { "progressed": "saturn", "natal": "sun", "type": "square", "orb": 0.9 }, ...
    ]
  }
}

说明：type 为相位英文键；orb 为容许度内偏差（度）。
错误时返回纯文本："[progression_chart] 错误：<错误说明>"。
"""
