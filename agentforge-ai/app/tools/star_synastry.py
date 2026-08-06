"""Synastry Chart Tool：合盘（Synastry）——两个人星盘的关系分析。

V2 扩展（《星盘分析扩展规划》1 节）：
- 输入：A/B 两方出生信息（各与 star_chart 一致，city 优先）
- 输出：双方本命盘 + 合盘相位（A 行星 × B 行星）+ 落宫叠加（A 入 B 宫 / B 入 A 宫）
- 口径复用 V1：Tropical + Geocentric + Placidus（默认），相位容许度同 V1
"""
import json

from app.tools.star_base import (
    ANGLES,
    EPHE_PATH,
    PLANET_IDS,
    aspect_info,
    house_of_longitude,
)
from app.tools.star_chart import calculate_chart


def _chart_kwargs(
    prefix: str,
    payload: dict,
    config: dict,
) -> dict:
    """按前缀从 payload 提取一方出生信息（a* / b*）。"""
    house_system = config.get("default_house_system") or payload.get("houseSystem", "") or "placidus"
    zodiac = config.get("default_zodiac") or payload.get("zodiac", "") or "tropical"
    ayanamsa = config.get("default_ayanamsa") or payload.get("ayanamsa", "") or "lahiri"
    orb_mode = config.get("default_orb_mode") or payload.get("orbMode", "") or "modern"
    return {
        "birth_date": payload.get(f"{prefix}BirthDate", ""),
        "birth_time": payload.get(f"{prefix}BirthTime", ""),
        "city": payload.get(f"{prefix}City", ""),
        "latitude": payload.get(f"{prefix}Latitude"),
        "longitude": payload.get(f"{prefix}Longitude"),
        "timezone": payload.get(f"{prefix}Timezone", ""),
        "house_system": house_system,
        "zodiac": zodiac,
        "ayanamsa": ayanamsa,
        "orb_mode": orb_mode,
        "aspect_types": payload.get("aspects"),
        "custom_orbs": payload.get("customOrbs"),
        "birth_text": payload.get(f"{prefix}BirthText", ""),
        "ephemeris_path": config.get("ephemeris_path") or EPHE_PATH,
    }


def _overlay(planets: dict, houses: dict, house_system: str, asc_lon: float) -> dict:
    """将一方行星放入另一方宫位结构。"""
    cusps = [houses[str(i + 1)]["cusp"] for i in range(12)]
    result: dict[str, dict] = {}
    for i in range(12):
        result[str(i + 1)] = {"sign": houses[str(i + 1)]["sign"], "planets": []}
    for pname, pdata in planets.items():
        h = house_of_longitude(cusps, house_system, asc_lon, pdata["longitude"])
        result[str(h)]["planets"].append(pname)
    return result


def calculate_synastry(
    a_birth_date: str,
    a_birth_time: str,
    a_city: str = "",
    a_latitude: float | None = None,
    a_longitude: float | None = None,
    a_timezone: str = "",
    a_birth_text: str = "",
    b_birth_date: str = "",
    b_birth_time: str = "",
    b_city: str = "",
    b_latitude: float | None = None,
    b_longitude: float | None = None,
    b_timezone: str = "",
    b_birth_text: str = "",
    house_system: str = "placidus",
    zodiac: str = "tropical",
    ayanamsa: str = "lahiri",
    orb_mode: str = "modern",
    aspect_types: list[str] | None = None,
    custom_orbs: dict | None = None,
    ephemeris_path: str = EPHE_PATH,
) -> dict:
    """合盘计算核心函数。

    Returns:
        合盘结果 dict：meta + personA/personB 完整本命盘 + synastry 区块。
    """
    chart_a = calculate_chart(
        birth_date=a_birth_date,
        birth_time=a_birth_time,
        city=a_city,
        latitude=a_latitude,
        longitude=a_longitude,
        timezone=a_timezone,
        house_system=house_system,
        zodiac=zodiac,
        ayanamsa=ayanamsa,
        orb_mode=orb_mode,
        aspects=aspect_types,
        custom_orbs=custom_orbs,
        birth_text=a_birth_text,
        ephemeris_path=ephemeris_path,
    )
    chart_b = calculate_chart(
        birth_date=b_birth_date,
        birth_time=b_birth_time,
        city=b_city,
        latitude=b_latitude,
        longitude=b_longitude,
        timezone=b_timezone,
        house_system=house_system,
        zodiac=zodiac,
        ayanamsa=ayanamsa,
        orb_mode=orb_mode,
        aspects=aspect_types,
        custom_orbs=custom_orbs,
        birth_text=b_birth_text,
        ephemeris_path=ephemeris_path,
    )

    # 合盘相位：A 行星 × B 行星
    inter_aspects: list[dict] = []
    for aname in PLANET_IDS:
        for bname in PLANET_IDS:
            info = aspect_info(
                chart_a["planets"][aname]["longitude"],
                chart_b["planets"][bname]["longitude"],
                aspect_keys=aspect_types,
                orb_mode=orb_mode,
                speed_a=chart_a["planets"][aname]["speed"],
                speed_b=chart_b["planets"][bname]["speed"],
                custom_orbs=custom_orbs,
            )
            if info:
                entry = {
                    "a": aname, "b": bname,
                    "type": info["typeEn"],
                    "angle": info["angle"],
                    "orb": info["orb"],
                }
                if info["direction"]:
                    entry["direction"] = info["direction"]
                inter_aspects.append(entry)

    # 落宫叠加
    a_in_b = _overlay(
        chart_a["planets"], chart_b["houses"],
        chart_b["meta"]["houseSystem"], chart_b["ascendant"]["longitude"],
    )
    b_in_a = _overlay(
        chart_b["planets"], chart_a["houses"],
        chart_a["meta"]["houseSystem"], chart_a["ascendant"]["longitude"],
    )

    # 行星 × 对方四轴相位
    angle_aspects: list[dict] = []
    for owner, chart, other in (("A", chart_a, chart_b), ("B", chart_b, chart_a)):
        for pname, pdata in chart["planets"].items():
            for angle_name in ANGLES:
                info = aspect_info(
                    pdata["longitude"], other[angle_name]["longitude"],
                    aspect_keys=aspect_types,
                    orb_mode=orb_mode,
                    speed_a=pdata["speed"],
                    custom_orbs=custom_orbs,
                )
                if info:
                    entry = {
                        "owner": owner,
                        "planet": pname,
                        "chart": "B" if owner == "A" else "A",
                        "angle": angle_name,
                        "type": info["typeEn"],
                        "angleDeg": info["angle"],
                        "orb": info["orb"],
                    }
                    if info["direction"]:
                        entry["direction"] = info["direction"]
                    angle_aspects.append(entry)

    meta = {
        "zodiac": chart_a["meta"]["zodiac"],
        "houseSystem": chart_a["meta"]["houseSystem"],
        "ephemeris": "pyswisseph",
        "ayanamsa": chart_a["meta"]["ayanamsa"],
        "personA": {
            "birthDateTime": chart_a["meta"]["birthDateTime"],
            "utDateTime": chart_a["meta"]["utDateTime"],
            "timezone": chart_a["meta"]["timezone"],
        },
        "personB": {
            "birthDateTime": chart_b["meta"]["birthDateTime"],
            "utDateTime": chart_b["meta"]["utDateTime"],
            "timezone": chart_b["meta"]["timezone"],
        },
    }

    return {
        "meta": meta,
        "personA": chart_a,
        "personB": chart_b,
        "synastry": {
            "aspects": inter_aspects,
            "aInBHouses": a_in_b,
            "bInAHouses": b_in_a,
            "angleAspects": angle_aspects,
        },
    }


def run(payload: dict, config: dict | None = None) -> str:
    """工具注册表调用入口：返回 JSON 字符串或错误文本。"""
    config = config or {}
    try:
        a = _chart_kwargs("a", payload, config)
        b = _chart_kwargs("b", payload, config)
        result = calculate_synastry(
            a_birth_date=a["birth_date"],
            a_birth_time=a["birth_time"],
            a_city=a["city"],
            a_latitude=a["latitude"],
            a_longitude=a["longitude"],
            a_timezone=a["timezone"],
            a_birth_text=a["birth_text"],
            b_birth_date=b["birth_date"],
            b_birth_time=b["birth_time"],
            b_city=b["city"],
            b_latitude=b["latitude"],
            b_longitude=b["longitude"],
            b_timezone=b["timezone"],
            b_birth_text=b["birth_text"],
            house_system=a["house_system"],
            zodiac=a["zodiac"],
            ayanamsa=a["ayanamsa"],
            orb_mode=a["orb_mode"],
            aspect_types=a["aspect_types"],
            custom_orbs=a["custom_orbs"],
            ephemeris_path=a["ephemeris_path"],
        )
        return json.dumps(result, ensure_ascii=False)
    except ValueError as exc:
        return f"[synastry_chart] 错误：{exc}"


SCHEMA = {
    "name": "synastry_chart",
    "description": (
        "合盘计算工具（V2）。输入 A/B 两方出生信息，"
        "输出双方本命盘、合盘相位（A 行星 × B 行星）、落宫叠加（A 入 B 宫 / B 入 A 宫）"
        "与行星 × 对方四轴相位，用于两人关系分析。口径与本命盘一致。"
    ),
    "parameters": {
        "aBirthDate": {"type": "string", "description": "A 方出生日期（公历），格式 YYYY-MM-DD"},
        "aBirthTime": {"type": "string", "description": "A 方出生时间（24h 制），格式 HH:MM"},
        "aCity": {
            "type": "string",
            "description": "A 方出生城市名（中文或英文）。城市在库时自动推断经纬度与时区",
            "required": False,
        },
        "aLatitude": {
            "type": "number",
            "description": "A 方纬度（-90~90）。城市不在库时使用",
            "required": False,
        },
        "aLongitude": {
            "type": "number",
            "description": "A 方经度（-180~180）。城市不在库时使用",
            "required": False,
        },
        "aTimezone": {
            "type": "string",
            "description": "A 方出生地 IANA 时区名。使用经纬度输入时必填",
            "required": False,
        },
        "aBirthText": {
            "type": "string",
            "description": "A 方自由文本输入（如 '1994-05-20 14:30 北京'）。提供时优先于结构化字段解析",
            "required": False,
        },
        "bBirthDate": {"type": "string", "description": "B 方出生日期（公历），格式 YYYY-MM-DD"},
        "bBirthTime": {"type": "string", "description": "B 方出生时间（24h 制），格式 HH:MM"},
        "bCity": {
            "type": "string",
            "description": "B 方出生城市名（中文或英文）。城市在库时自动推断经纬度与时区",
            "required": False,
        },
        "bLatitude": {
            "type": "number",
            "description": "B 方纬度（-90~90）。城市不在库时使用",
            "required": False,
        },
        "bLongitude": {
            "type": "number",
            "description": "B 方经度（-180~180）。城市不在库时使用",
            "required": False,
        },
        "bTimezone": {
            "type": "string",
            "description": "B 方出生地 IANA 时区名。使用经纬度输入时必填",
            "required": False,
        },
        "bBirthText": {
            "type": "string",
            "description": "B 方自由文本输入（如 '1995-08-08 08:00 上海'）。提供时优先于结构化字段解析",
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
synastry_chart 工具出参 JSON 结构定义
=====================================

成功时返回 JSON 字符串：

{
  "meta": {
    "zodiac": "tropical", "houseSystem": "placidus",
    "ephemeris": "pyswisseph", "ayanamsa": null,
    "personA": { "birthDateTime": "...", "utDateTime": "...", "timezone": "Asia/Shanghai" },
    "personB": { "birthDateTime": "...", "utDateTime": "...", "timezone": "Asia/Shanghai" }
  },
  "personA": { ...完整本命盘（同 star_chart 出参）... },
  "personB": { ...完整本命盘... },
  "synastry": {
    "aspects": [  // 合盘相位：A 行星 × B 行星
      { "a": "venus", "b": "mars", "type": "trine", "orb": 0.8 },
      { "a": "sun", "b": "moon", "type": "square", "orb": 2.3 }
    ],
    "aInBHouses": {  // A 方行星落在 B 方宫位
      "1": { "sign": "天秤座", "planets": ["venus"] }, ...
    },
    "bInAHouses": {  // B 方行星落在 A 方宫位
      "7": { "sign": "白羊座", "planets": ["mars"] }, ...
    },
    "angleAspects": [  // 行星 × 对方四轴
      { "owner": "A", "planet": "jupiter", "chart": "B", "angle": "ascendant", "type": "conjunction", "orb": 2.1 }, ...
    ]
  }
}

说明：type 为相位英文键；orb 为容许度内偏差（度）。
错误时返回纯文本："[synastry_chart] 错误：<错误说明>"。
"""
