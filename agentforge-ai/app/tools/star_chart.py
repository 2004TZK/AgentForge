"""StarChart Tool：本命盘排盘计算（瑞士星历表 pyswisseph）。

项目面向中国用户，城市库以中国大陆城市为主（含港澳台）。
时区处理聚焦中国场景：Asia/Shanghai (UTC+8) + Asia/Urumqi (UTC+6)，
历史夏令时覆盖中国 1986-1991 DST。

- 入参：出生日期/时间/地点（城市名或经纬度 + 时区），可选宫位制/黄道类型
- 出参：结构化 JSON（meta + planets + points + houses + aspects + patterns）
- 口径：Tropical + Geocentric + Placidus（默认），可切换整宫制 / 恒星黄道
- V3 增强：多宫位制（10 种）、多 Ayanamsa、虚点/小行星、次要相位、
  现代/古典容许度、入相/出相、17 种格局判定
- 依赖：pyswisseph（AGPL-3.0）、tzdata（python:3.12-slim 需显式安装）
- 历书数据：app/tools/data/ephe/ 下的 sepl_18.se1 + semo_18.se1（覆盖 1800-2399）
"""
import json

from app.tools.star_base import (
    ANGLES,
    DEFAULT_POINTS,
    EPHE_PATH,
    assign_houses,
    assign_point_houses,
    compute_aspects,
    find_patterns,
    houses_and_angles,
    planet_orb,
    planets_at_jd,
    points_at_jd,
    prepare_chart_inputs,
    resolve_aspect_keys,
)


def calculate_chart(
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
    aspects: list[str] | None = None,
    custom_orbs: dict | None = None,
    aspect_targets: list[str] | None = None,
    points: list[str] | None = None,
    birth_text: str = "",
    ephemeris_path: str = EPHE_PATH,
) -> dict:
    """排盘计算核心函数。

    Args:
        birth_date: 出生日期，格式 YYYY-MM-DD
        birth_time: 出生时间，格式 HH:MM
        city: 城市名（中/英），城市在库时自动推断时区
        latitude: 纬度（城市不在库时使用）
        longitude: 经度（城市不在库时使用）
        timezone: IANA 时区名（手动经纬度时必填）
        house_system: 宫位制，placidus 或 whole_sign
        zodiac: 黄道类型，tropical 或 sidereal
        ayanamsa: 恒星黄道 Ayanamsa（默认 lahiri；raman/krishnamurti/fagan_bradley 等）
        orb_mode: 容许度流派，modern（统一）或 classical（按星体）
        aspects: 启用的相位类型列表（缺省仅五大主相位）
        custom_orbs: 自定义相位容许度 {相位键: 度}
        aspect_targets: 参与相位计算的目标键（行星/虚点/四轴名，缺省仅十大行星）
        points: 启用的虚点/小行星列表（缺省北交点+南交点）
        birth_text: 自由文本输入（如 "1994-05-20 14:30 北京"），供工作流直接传用户消息
        ephemeris_path: 历书数据目录（默认 app/tools/data/ephe/）

    Returns:
        排盘结果 dict，结构见 SCHEMA 出参说明。

    Raises:
        ValueError: 输入校验失败（缺时间、城市不在库、缺时区等）
    """
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

    # 十大星体
    planets = planets_at_jd(ctx["swe"], ctx["jd"], ctx["flags"])

    # 四轴与宫位（Placidus，高纬度自动降级整宫制）
    houses, angles, house_system, fallback, asc_lon, _mc_lon, vertex_lon = houses_and_angles(
        ctx["swe"], ctx["jd"], ctx["lat"], ctx["lon"], ctx["house_system"]
    )
    assign_houses(planets, houses, house_system, asc_lon)

    # 虚点 / 小行星
    point_list = points or DEFAULT_POINTS
    point_data = points_at_jd(
        ctx["swe"], ctx["jd"], ctx["flags"],
        asc_lon=asc_lon,
        sun_lon=planets["sun"]["longitude"],
        moon_lon=planets["moon"]["longitude"],
        vertex_lon=vertex_lon,
        points=point_list,
    )
    assign_point_houses(point_data, houses, house_system, asc_lon)

    # 相位：默认仅行星；可扩展至虚点/四轴
    targets = aspect_targets or list(planets)
    positions: dict = {}
    for name in targets:
        if name in planets:
            positions[name] = {
                "longitude": planets[name]["longitude"],
                "speed": planets[name]["speed"],
                "orb": planet_orb(name, orb_mode),
            }
        elif name in point_data:
            positions[name] = {
                "longitude": point_data[name]["longitude"],
                "speed": point_data[name].get("speed"),
                "orb": planet_orb(name, orb_mode),
            }
        elif name in ANGLES:
            positions[name] = {"longitude": angles[name]["longitude"]}

    aspect_keys = resolve_aspect_keys(aspects)
    aspect_list = compute_aspects(
        positions,
        aspect_keys=list(aspect_keys),
        orb_mode=orb_mode,
        custom_orbs=custom_orbs,
    )
    patterns = find_patterns(
        planets,
        aspect_keys=list(aspect_keys),
        orb_mode=orb_mode,
        custom_orbs=custom_orbs,
    )

    return {
        "meta": {
            "zodiac": ctx["zodiac"],
            "houseSystem": house_system,
            "houseSystemFallback": fallback,
            "timezone": ctx["tz_name"],
            "ephemeris": "pyswisseph",
            "ayanamsa": ctx["ayanamsa"],
            "orbMode": orb_mode,
            "aspectsEnabled": list(aspect_keys),
            "birthDateTime": ctx["local_dt"].isoformat(),
            "utDateTime": ctx["utc_dt"].strftime("%Y-%m-%dT%H:%M:%SZ"),
        },
        **angles,
        "planets": planets,
        "points": point_data,
        "houses": houses,
        "aspects": aspect_list,
        "patterns": patterns,
        "birthText": birth_text or None,
    }


def run(payload: dict, config: dict | None = None) -> str:
    """工具注册表调用入口：payload 为 LLM 参数（camelCase），返回 JSON 字符串或错误文本。

    - config.ephemeris_path：历书目录覆盖
    - config.default_house_system / default_zodiac：智能体级默认配置
    - 校验失败返回 "[star_chart] 错误：<说明>"（与出参文档一致），不抛异常
    """
    config = config or {}
    try:
        result = calculate_chart(
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
            aspects=payload.get("aspects"),
            custom_orbs=payload.get("customOrbs"),
            aspect_targets=payload.get("aspectTargets"),
            points=payload.get("points"),
            birth_text=payload.get("birthText", ""),
            ephemeris_path=config.get("ephemeris_path") or EPHE_PATH,
        )
        return json.dumps(result, ensure_ascii=False)
    except ValueError as exc:
        return f"[star_chart] 错误：{exc}"


# ──────────────────────────── Schema 定稿 ────────────────────────────

SCHEMA = {
    "name": "star_chart",
    "description": (
        "本命盘排盘计算工具。输入出生日期、时间、地点，"
        "输出十大星体位置、虚点、四轴、十二宫位、相位、格局等结构化数据。"
        "口径：回归黄道(Tropical) + 地心(Geocentric) + Placidus 宫位制（默认）；"
        "支持 10 种宫位制、多 Ayanamsa、次要相位、现代/古典容许度、入相/出相。"
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
            "description": "IANA 时区名，如 Asia/Shanghai。使用经纬度输入时必填（经纬度无法推导时区）",
            "required": False,
        },
        "houseSystem": {
            "type": "string",
            "description": (
                "宫位制：placidus（默认）/ whole_sign（整宫制）/ equal（等宫制）/ "
                "koch / regiomontanus / campanus / porphyry / topocentric / alcabitius / morinus"
            ),
            "required": False,
        },
        "zodiac": {
            "type": "string",
            "description": "黄道类型：tropical（默认，回归黄道）或 sidereal（恒星黄道）",
            "required": False,
        },
        "ayanamsa": {
            "type": "string",
            "description": (
                "恒星黄道 Ayanamsa（zodiac=sidereal 时生效）："
                "lahiri（默认）/ raman / krishnamurti / fagan_bradley / deluce / "
                "ushashi / j2000 / j1900 / b1950 / suryasiddhanta / true_citra / ss_revati"
            ),
            "required": False,
        },
        "orbMode": {
            "type": "string",
            "description": (
                "相位容许度流派：modern（默认，统一 8/8/8/8/6，次要相位 2°）"
                "或 classical（按星体星光范围：日 15° 月 12° 水 7° 金/火 7-8° 木/土 9° 等）"
            ),
            "required": False,
        },
        "aspects": {
            "type": "array",
            "items": {"type": "string"},
            "description": (
                "启用的相位类型（缺省仅五大主相位）。可选：conjunction/semi_sextile/"
                "semi_square/sextile/quintile/square/trine/sesquiquadrate/biquintile/"
                "quincunx/opposition。注意：上帝之指需开启 quincunx，小三角需开启 semi_sextile"
            ),
            "required": False,
        },
        "customOrbs": {
            "type": "object",
            "description": "自定义相位容许度，如 {\"conjunction\": 10, \"quincunx\": 3}",
            "required": False,
        },
        "aspectTargets": {
            "type": "array",
            "items": {"type": "string"},
            "description": (
                "参与相位计算的目标键（缺省仅十大行星）。"
                "可加入虚点（north_node/south_node/part_of_fortune 等）与四轴（ascendant/midheaven/descendant/imum_coeli）"
            ),
            "required": False,
        },
        "points": {
            "type": "array",
            "items": {"type": "string"},
            "description": (
                "启用的虚点/小行星（缺省北交点+南交点）。可选：north_node/south_node/"
                "true_node/true_south_node/lilith/true_lilith/part_of_fortune/vertex/"
                "chiron/ceres/pallas/juno/vesta（小行星需 seas_18.se1 历书数据）"
            ),
            "required": False,
        },
        "birthText": {
            "type": "string",
            "description": "自由文本输入（如 '1994-05-20 14:30 北京'），供工作流节点直接传用户消息。提供时优先于结构化字段解析",
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


# ──────────────────────── 出参 Schema 文档 ────────────────────────
# 以下为出参 JSON 结构定义，供 LLM/前端/测试参考。
# 实际返回值为 json.dumps(result, ensure_ascii=False) 字符串。

OUTPUT_SCHEMA_DOC = """
star_chart 工具出参 JSON 结构定义
=================================

成功时返回 JSON 字符串，结构如下：

{
  "meta": {
    "zodiac": "tropical",              // 黄道类型：tropical | sidereal
    "houseSystem": "placidus",         // 宫位制：placidus | whole_sign
    "houseSystemFallback": false,      // 是否因高纬度降级为整宫制
    "timezone": "Asia/Shanghai",       // IANA 时区名
    "ephemeris": "pyswisseph",         // 历书引擎标识
    "ayanamsa": null,                  // 恒星黄道 Ayanamsa（仅 sidereal 时有值，如 "Lahiri"）
    "orbMode": "modern",               // 容许度流派：modern | classical
    "aspectsEnabled": ["conjunction", "sextile", "square", "trine", "opposition"],
    "birthDateTime": "1994-05-20T14:30:00+08:00",  // 出生当地时间（ISO 8601 带时区偏移）
    "utDateTime": "1994-05-20T06:30:00Z"            // UTC 时间（用于计算）
  },

  "ascendant": {
    "sign": "天秤座",                   // 中文星座名
    "signIndex": 6,                    // 星座索引 0-11（0=白羊）
    "degree": 12.5,                    // 宫内度数 0-29.999
    "longitude": 192.5                 // 黄道经度 0-359.999
  },

  "midheaven": {
    "sign": "巨蟹座",
    "signIndex": 3,
    "degree": 23.4,
    "longitude": 113.4
  },

  "descendant": {
    "sign": "白羊座",
    "signIndex": 0,
    "degree": 12.5,
    "longitude": 12.5
  },

  "imum_coeli": {
    "sign": "摩羯座",
    "signIndex": 9,
    "degree": 23.4,
    "longitude": 293.4
  },

  "planets": {
    "sun": {
      "sign": "金牛座",
      "signIndex": 1,
      "house": 9,                      // 所在宫位 1-12
      "degree": 29.4,                  // 宫内度数（星座内）0-29.999
      "longitude": 59.4,               // 黄道经度 0-359.999
      "speed": 0.955,                  // 运行速度（度/天，用于入相/出相判定）
      "retrograde": false              // 是否逆行
    },
    "moon":     { "sign": "双子座", "signIndex": 2, "house": 10, "degree": 3.8,  "longitude": 63.8,  "speed": 13.1, "retrograde": false },
    "mercury":  { "sign": "双子座", "signIndex": 2, "house": 10, "degree": 15.2, "longitude": 75.2,  "speed": 1.3,  "retrograde": false },
    "venus":    { "sign": "白羊座", "signIndex": 0, "house": 8,  "degree": 5.1,  "longitude": 5.1,   "speed": 1.2,  "retrograde": false },
    "mars":     { "sign": "白羊座", "signIndex": 0, "house": 7,  "degree": 28.3, "longitude": 28.3,  "speed": 0.6,  "retrograde": false },
    "jupiter":  { "sign": "天蝎座", "signIndex": 7, "house": 2,  "degree": 10.5, "longitude": 220.5, "speed": -0.05, "retrograde": true  },
    "saturn":   { "sign": "双鱼座", "signIndex": 11,"house": 5,  "degree": 18.7, "longitude": 348.7, "speed": 0.03, "retrograde": false },
    "uranus":   { "sign": "摩羯座", "signIndex": 9, "house": 3,  "degree": 22.1, "longitude": 292.1, "speed": 0.02, "retrograde": false },
    "neptune":  { "sign": "摩羯座", "signIndex": 9, "house": 3,  "degree": 22.4, "longitude": 292.4, "speed": 0.01, "retrograde": false },
    "pluto":    { "sign": "射手座", "signIndex": 8, "house": 2,  "degree": 27.5, "longitude": 267.5, "speed": -0.01, "retrograde": true  }
  },

  "points": {
    "north_node": { "sign": "射手座", "signIndex": 8, "house": 2, "degree": 23.7,
                    "longitude": 263.7, "speed": -0.05, "retrograde": true },
    "south_node": { "sign": "双子座", "signIndex": 2, "house": 8, "degree": 23.7,
                    "longitude": 83.7, "speed": -0.05, "retrograde": true }
  },

  "houses": {
    "1":  { "cusp": 192.5, "sign": "天秤座",   "planets": [] },
    "2":  { "cusp": 215.0, "sign": "天蝎座",   "planets": ["jupiter"] },
    "3":  { "cusp": 243.0, "sign": "射手座",   "planets": ["uranus", "neptune"] },
    "4":  { "cusp": 273.0, "sign": "摩羯座",   "planets": [] },
    "5":  { "cusp": 303.0, "sign": "水瓶座",   "planets": ["saturn"] },
    "6":  { "cusp": 333.0, "sign": "双鱼座",   "planets": [] },
    "7":  { "cusp": 12.5,  "sign": "白羊座",   "planets": ["mars"] },
    "8":  { "cusp": 35.0,  "sign": "金牛座",   "planets": ["venus"] },
    "9":  { "cusp": 59.4,  "sign": "金牛座",   "planets": ["sun"] },
    "10": { "cusp": 63.8,  "sign": "双子座",   "planets": ["moon", "mercury"] },
    "11": { "cusp": 93.0,  "sign": "巨蟹座",   "planets": [] },
    "12": { "cusp": 123.0, "sign": "狮子座",   "planets": [] }
  },

  "aspects": [
    { "p1": "sun", "p2": "moon",     "type": "三分相", "typeEn": "trine",       "angle": 120, "orb": 4.4, "direction": "separating" },
    { "p1": "sun", "p2": "saturn",   "type": "四分相", "typeEn": "square",       "angle": 90,  "orb": 1.9, "direction": "applying" },
    { "p1": "moon","p2": "mercury",  "type": "合相",   "typeEn": "conjunction",  "angle": 0,   "orb": 3.6, "direction": "separating" }
  ],

  "patterns": [
    { "type": "星群", "scope": "house", "house": 10, "planets": ["moon", "mercury"] },
    { "type": "T三角", "planets": ["sun", "saturn", "moon"], "apex": "saturn" },
    { "type": "碗型", "span": 174.3, "rim": "sun" }
  ],

  "birthText": null                    // 原始自由文本输入（若使用了 birthText 参数）
}

错误时返回纯文本字符串（非 JSON），格式：
  "[star_chart] 错误：<错误说明>"

错误场景与文本：
  - 缺出生时间 → "[star_chart] 错误：缺少出生时间，无法计算上升点与宫位。请提供出生时间（格式 HH:MM）。"
  - 城市不在库 → "[star_chart] 错误：城市 'xxx' 不在内置城市库中。请改用经纬度输入（latitude + longitude + timezone）。"
  - 手动经纬度缺时区 → "[star_chart] 错误：使用经纬度输入时必须提供 timezone（IANA 时区名，如 Asia/Shanghai）。"
  - 历书数据缺失 → "[star_chart] 错误：瑞士星历表数据文件缺失，请联系管理员检查 ephe 目录。"
  - 年份超范围 → "[star_chart] 错误：出生年份超出历书覆盖范围（1800-2399）。"
  - Placidus 高纬度降级 → 正常返回 JSON，meta.houseSystemFallback = true，houseSystem = "whole_sign"
"""
