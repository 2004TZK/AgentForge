"""Transit Chart Tool：行运（Transits）——指定时刻行星与本命盘的互动（"近期运势"）。

V2 扩展（《星盘分析扩展规划》1 节）：
- 输入：本命盘信息（与 star_chart 一致）+ 行运日期/时间（缺省当前时刻）
- 输出：行运行星位置（含落本命宫位）+ 行运与本命行星/四轴相位 + 本命盘
- 口径复用 V1：Tropical + Geocentric + Placidus（默认），相位容许度同 V1
"""
import json
from datetime import datetime
from zoneinfo import ZoneInfo

from app.tools.star_base import (
    ANGLES,
    DEFAULT_POINTS,
    EPHE_PATH,
    aspect_info,
    build_ephemeris,
    house_of_longitude,
    julday,
    local_dt_to_utc,
    planets_at_jd,
    points_at_jd,
    validate_date_time,
)
from app.tools.star_chart import calculate_chart

# 行运四轴中文名（LLM 解读用）
ANGLE_ZH = {
    "ascendant": "上升点",
    "midheaven": "天顶",
    "descendant": "下降点",
    "imum_coeli": "天底",
}


def _transit_moment(
    swe,
    transit_date: str,
    transit_time: str,
    transit_timezone: str,
    flags: int,
) -> tuple[float, str, str]:
    """行运时刻 → (jd, local_dt_iso, utc_dt_iso)。缺省使用当前 UTC 时刻。"""
    tz_name = transit_timezone or "UTC"
    if not transit_date:
        now = datetime.now().astimezone()
        utc_now = now.astimezone(ZoneInfo("UTC"))
        jd = julday(swe, utc_now)
        return jd, now.isoformat(), utc_now.strftime("%Y-%m-%dT%H:%M:%SZ")
    if not transit_time:
        transit_time = "12:00"  # 只给日期时默认当地正午采样
    year, month, day, hour, minute = validate_date_time(transit_date, transit_time)
    local_dt, utc_dt = local_dt_to_utc(year, month, day, hour, minute, tz_name)
    return julday(swe, utc_dt), local_dt.isoformat(), utc_dt.strftime("%Y-%m-%dT%H:%M:%SZ")


def calculate_transit(
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
    transit_date: str = "",
    transit_time: str = "",
    transit_timezone: str = "UTC",
    ephemeris_path: str = EPHE_PATH,
) -> dict:
    """行运计算核心函数。

    行运口径：指定时刻（默认当前时刻）的行星位置，与本命盘行星/四轴计算主相位，
    并按本命宫位制确定行运行星的"落宫"（行运经过的人生领域）。

    Returns:
        行运结果 dict：meta（含行运时刻）+ 本命盘顶层字段 + transit 区块。
    """
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
    swe, flags, _ayanamsa = build_ephemeris(natal["meta"]["zodiac"], ephemeris_path)
    jd_t, local_iso, utc_iso = _transit_moment(
        swe, transit_date, transit_time, transit_timezone, flags
    )

    transit_planets = planets_at_jd(swe, jd_t, flags)
    transit_points = points_at_jd(
        swe, jd_t, flags,
        asc_lon=natal["ascendant"]["longitude"],
        sun_lon=transit_planets["sun"]["longitude"],
        moon_lon=transit_planets["moon"]["longitude"],
        points=points or DEFAULT_POINTS,
    )
    natal_house_system = natal["meta"]["houseSystem"]
    natal_cusps = [natal["houses"][str(i + 1)]["cusp"] for i in range(12)]
    asc_lon = natal["ascendant"]["longitude"]

    # 行运行星 → 本命宫位
    houses: dict[str, dict] = {}
    for i in range(12):
        houses[str(i + 1)] = {"sign": natal["houses"][str(i + 1)]["sign"], "planets": []}
    for pname, pdata in transit_planets.items():
        h = house_of_longitude(natal_cusps, natal_house_system, asc_lon, pdata["longitude"])
        pdata["natalHouse"] = h
        houses[str(h)]["planets"].append(pname)
    for pname, pdata in transit_points.items():
        h = house_of_longitude(natal_cusps, natal_house_system, asc_lon, pdata["longitude"])
        pdata["natalHouse"] = h

    # 行运 → 本命行星相位
    aspects: list[dict] = []
    for tname, tdata in transit_planets.items():
        for nname, ndata in natal["planets"].items():
            info = aspect_info(
                tdata["longitude"], ndata["longitude"],
                aspect_keys=aspect_types,
                orb_mode=orb_mode,
                speed_a=tdata["speed"],
                speed_b=ndata["speed"],
                custom_orbs=custom_orbs,
            )
            if info:
                entry = {
                    "transit": tname,
                    "natal": nname,
                    "type": info["typeEn"],
                    "angle": info["angle"],
                    "orb": info["orb"],
                }
                if info["direction"]:
                    entry["direction"] = info["direction"]
                aspects.append(entry)

    # 行运 → 本命四轴相位
    angle_aspects: list[dict] = []
    for tname, tdata in transit_planets.items():
        for angle_name in ANGLES:
            info = aspect_info(
                tdata["longitude"], natal[angle_name]["longitude"],
                aspect_keys=aspect_types,
                orb_mode=orb_mode,
                speed_a=tdata["speed"],
                custom_orbs=custom_orbs,
            )
            if info:
                entry = {
                    "transit": tname,
                    "angle": angle_name,
                    "type": info["typeEn"],
                    "angleDeg": info["angle"],
                    "orb": info["orb"],
                }
                if info["direction"]:
                    entry["direction"] = info["direction"]
                angle_aspects.append(entry)

    meta = dict(natal["meta"])
    meta.update({
        "transitDate": transit_date or None,
        "transitTime": transit_time or None,
        "transitTimezone": transit_timezone,
        "transitDateTime": local_iso,
        "transitUtDateTime": utc_iso,
    })

    return {
        **natal,
        "meta": meta,
        "transit": {
            "planets": transit_planets,
            "points": transit_points,
            "houses": houses,
            "aspects": aspects,
            "angleAspects": angle_aspects,
        },
    }


def run(payload: dict, config: dict | None = None) -> str:
    """工具注册表调用入口：返回 JSON 字符串或错误文本。"""
    config = config or {}
    try:
        result = calculate_transit(
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
            transit_date=payload.get("transitDate", ""),
            transit_time=payload.get("transitTime", ""),
            transit_timezone=payload.get("transitTimezone", "") or "UTC",
            ephemeris_path=config.get("ephemeris_path") or EPHE_PATH,
        )
        return json.dumps(result, ensure_ascii=False)
    except ValueError as exc:
        return f"[transit_chart] 错误：{exc}"


SCHEMA = {
    "name": "transit_chart",
    "description": (
        "行运计算工具（V2）。输入本命盘信息与行运日期/时间（缺省当前时刻），"
        "输出行运行星位置（含落本命宫位）、行运与本命行星/四轴相位，用于'近期运势'解读。"
        "口径与本命盘一致：回归黄道 + Placidus（默认），支持多宫位制/多 Ayanamsa/次要相位。"
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
            "description": "行运虚点/小行星（缺省北交点+南交点）",
            "required": False,
        },
        "birthText": {
            "type": "string",
            "description": "本命盘自由文本输入（如 '1994-05-20 14:30 北京'）。提供时优先于结构化字段解析",
            "required": False,
        },
        "transitDate": {
            "type": "string",
            "description": "行运日期，格式 YYYY-MM-DD；缺省为当前时刻",
            "required": False,
        },
        "transitTime": {
            "type": "string",
            "description": "行运时间（24h 制），格式 HH:MM；只给日期时默认当地正午采样",
            "required": False,
        },
        "transitTimezone": {
            "type": "string",
            "description": "行运时刻所在 IANA 时区，默认 UTC",
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
transit_chart 工具出参 JSON 结构定义
====================================

成功时返回 JSON 字符串。顶层字段与本命盘 star_chart 一致（meta/四轴/planets/houses/aspects/patterns
为本命盘数据），另含 transit 区块：

{
  "meta": {  // 本命盘 meta + 行运时刻
    ...,
    "transitDate": "2026-08-05",
    "transitTime": "12:00",
    "transitTimezone": "UTC",
    "transitDateTime": "2026-08-05T12:00:00+00:00",
    "transitUtDateTime": "2026-08-05T12:00:00Z"
  },

    "transit": {
    "planets": {  // 行运行星位置（含 natalHouse：落本命宫位）
      "sun": { "sign": "狮子座", "signIndex": 4, "degree": 13.2,
               "longitude": 133.2, "speed": 0.95, "retrograde": false, "natalHouse": 5 },
      ...
    },
    "points": {  // 行运虚点（含 natalHouse）
      "north_node": { "sign": "狮子座", "signIndex": 4, "degree": 20.1,
                      "longitude": 140.1, "natalHouse": 6 }, ...
    },
    "houses": {  // 行运行星按本命宫位分布
      "1": { "sign": "天秤座", "planets": [] },
      "5": { "sign": "水瓶座", "planets": ["sun", "mercury"] },
      ...
    },
    "aspects": [  // 行运 → 本命行星相位
      { "transit": "saturn", "natal": "sun", "type": "square", "angle": 90, "orb": 1.2, "direction": "applying" },
      { "transit": "jupiter", "natal": "moon", "type": "trine", "angle": 120, "orb": 0.8, "direction": "separating" }
    ],
    "angleAspects": [  // 行运 → 本命四轴相位
      { "transit": "jupiter", "angle": "ascendant", "type": "conjunction", "angleDeg": 0, "orb": 2.1 }
    ]
  }
}

说明：type 为相位英文键（conjunction/opposition/trine/square/sextile），orb 为容许度内偏差（度）。
错误时返回纯文本："[transit_chart] 错误：<错误说明>"。
"""
