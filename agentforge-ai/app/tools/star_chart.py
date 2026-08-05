"""StarChart Tool：本命盘排盘计算（瑞士星历表 pyswisseph）。

项目面向中国用户，城市库以中国大陆城市为主（含港澳台）。
时区处理聚焦中国场景：Asia/Shanghai (UTC+8) + Asia/Urumqi (UTC+6)，
历史夏令时覆盖中国 1986-1991 DST。

- 入参：出生日期/时间/地点（城市名或经纬度 + 时区），可选宫位制/黄道类型
- 出参：结构化 JSON（meta + planets + houses + aspects + patterns）
- 口径：Tropical + Geocentric + Placidus（默认），可切换整宫制 / 恒星黄道
- 依赖：pyswisseph（AGPL-3.0）、tzdata（python:3.12-slim 需显式安装）
- 历书数据：app/tools/data/ephe/ 下的 sepl_18.se1 + semo_18.se1（覆盖 1800-2399）
"""
import json
import re
import unicodedata
from datetime import datetime
from itertools import combinations
from pathlib import Path
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

# 历书数据目录（相对于本文件）
EPHE_PATH = str(Path(__file__).parent / "data" / "ephe")

# 城市库 JSON 路径
CITIES_PATH = str(Path(__file__).parent / "data" / "cities.json")

# 默认相位容许度（度）——V1 统一值，暂不做星体差异
DEFAULT_ORBS = {
    "conjunction": 8.0,  # 合相
    "opposition": 8.0,   # 对分相
    "trine": 8.0,        # 三分相
    "square": 8.0,       # 四分相
    "sextile": 6.0,      # 六分相
}

# 十大星体 pyswisseph 常量映射
PLANET_IDS = {
    "sun": 0, "moon": 1, "mercury": 2, "venus": 3, "mars": 4,
    "jupiter": 5, "saturn": 6, "uranus": 7, "neptune": 8, "pluto": 9,
}

# pyswisseph 2.10.x API 要点（已实测验证）：
#   swe.calc_ut(jd, pid) → ((lon, lat, dist, lon_speed, lat_speed, dist_speed), ret_flags)
#     取黄经：xx[0] = result[0][0]
#   swe.houses(jd, lat, lon, b'P') → (cusps_12_tuple, ascmc_8_tuple)
#     ASC = ascmc[0], MC = ascmc[1]；注意返回 2 元组，非 3 元组
#   swe.set_sid_mode(swe.SIDM_LAHIRI)  # 非 set_sidmode
#   高纬度（~66°N+）Placidus 抛异常 → 改用 b'W' (Whole Sign) 降级

# 相位角度（度）
ASPECT_ANGLES = {
    "conjunction": 0.0,
    "sextile": 60.0,
    "square": 90.0,
    "trine": 120.0,
    "opposition": 180.0,
}

# 出生信息自由文本解析
_DATE_RE = re.compile(r"(\d{4})\s*[-/.年]\s*(\d{1,2})\s*[-/.月]\s*(\d{1,2})\s*日?")
_TIME_RE = re.compile(r"(\d{1,2})\s*[:点时]\s*(\d{1,2})\s*分?")

# 四轴名称
ANGLES = ["ascendant", "midheaven", "descendant", "imum_coeli"]

# 黄道十二宫中文名（索引 0 = 白羊座）
SIGNS_ZH = [
    "白羊座", "金牛座", "双子座", "巨蟹座", "狮子座", "处女座",
    "天秤座", "天蝎座", "射手座", "摩羯座", "水瓶座", "双鱼座",
]

# 相位中文名
ASPECT_TYPES_ZH = {
    "conjunction": "合相",
    "opposition": "对分相",
    "trine": "三分相",
    "square": "四分相",
    "sextile": "六分相",
}


def _load_cities() -> list[dict]:
    """加载城市库 JSON。"""
    with open(CITIES_PATH, encoding="utf-8") as f:
        return json.load(f)


def _normalize_en(text: str) -> str:
    """英文名归一化：小写 + 去除重音（如 Ürümqi → urumqi）。"""
    return "".join(
        ch for ch in unicodedata.normalize("NFKD", text)
        if not unicodedata.combining(ch)
    ).lower().strip()


def _lookup_city(name: str) -> dict | None:
    """按中文名或英文名查找城市，返回 {lat, lng, tz} 或 None。"""
    cities = _load_cities()
    name_zh = name.strip()
    name_en = _normalize_en(name)
    for c in cities:
        if c["zh"] == name_zh or _normalize_en(c["en"]) == name_en:
            return {"lat": c["lat"], "lng": c["lng"], "tz": c["tz"]}
    return None


def _swe():
    """延迟导入 pyswisseph；未安装时抛出可读 ValueError（不影响注册表/应用启动）。"""
    try:
        import swisseph as swe
    except ImportError as exc:
        raise ValueError(
            "pyswisseph 未安装，无法进行星盘计算。请执行 pip install pyswisseph tzdata"
        ) from exc
    return swe


def _parse_birth_text(text: str) -> tuple[str, str, str]:
    """从自由文本解析出生信息，返回 (birth_date, birth_time, city)。"""
    m = _DATE_RE.search(text)
    if not m:
        raise ValueError("无法从输入中解析出生日期（格式 YYYY-MM-DD）。")
    birth_date = f"{int(m.group(1)):04d}-{int(m.group(2)):02d}-{int(m.group(3)):02d}"
    t = _TIME_RE.search(text)
    if not t:
        raise ValueError("缺少出生时间，无法计算上升点与宫位。请提供出生时间（格式 HH:MM）。")
    birth_time = f"{int(t.group(1)):02d}:{int(t.group(2)):02d}"
    rest = _DATE_RE.sub(" ", text)
    rest = _TIME_RE.sub(" ", rest)
    city = re.sub(r"[\s,，。.;；:：]+", " ", rest).strip()
    return birth_date, birth_time, city


def _resolve_location(
    city: str, latitude: float | None, longitude: float | None, timezone: str
) -> tuple[float, float, str]:
    """解析出生地点：city 优先（城市库推断经纬度+时区），否则用经纬度（必须带时区）。"""
    if city:
        loc = _lookup_city(city)
        if loc is None:
            raise ValueError(
                f"城市 '{city}' 不在内置城市库中。请改用经纬度输入（latitude + longitude + timezone）。"
            )
        return loc["lat"], loc["lng"], loc["tz"]
    if latitude is None or longitude is None:
        raise ValueError("缺少出生地点：请提供城市名（如 北京），或经纬度 + timezone。")
    lat, lon = float(latitude), float(longitude)
    if not (-90 <= lat <= 90) or not (-180 <= lon <= 180):
        raise ValueError("经纬度非法：纬度范围 -90~90，经度范围 -180~180。")
    if not timezone:
        raise ValueError("使用经纬度输入时必须提供 timezone（IANA 时区名，如 Asia/Shanghai）。")
    return lat, lon, timezone


def _angle_point(longitude: float) -> dict:
    """黄经 → 四轴点位结构。"""
    lon = longitude % 360
    return {
        "sign": SIGNS_ZH[int(lon // 30) % 12],
        "signIndex": int(lon // 30) % 12,
        "degree": round(lon % 30, 4),
        "longitude": round(lon, 4),
    }


def _aspect_between(lon_a: float, lon_b: float) -> tuple[str, float] | None:
    """计算两黄经之间是否构成主相位，返回 (typeEn, orb)，否则 None。"""
    diff = abs(lon_a - lon_b) % 360
    diff = min(diff, 360 - diff)
    for key, angle in ASPECT_ANGLES.items():
        orb = DEFAULT_ORBS[key]
        if abs(diff - angle) <= orb + 1e-9:
            return key, round(abs(diff - angle), 4)
    return None


def _find_patterns(planets: dict) -> list[dict]:
    """基于相位表判定格局：大三角 / T 三角 / 大十字 / 星群（同宫、同星座）。"""
    patterns: list[dict] = []
    names = list(PLANET_IDS)

    # 星群：同宫 ≥3 或同星座 ≥3
    house_groups: dict[int, list[str]] = {}
    sign_groups: dict[int, list[str]] = {}
    for pname in names:
        house_groups.setdefault(planets[pname]["house"], []).append(pname)
        sign_groups.setdefault(planets[pname]["signIndex"], []).append(pname)
    for h, members in house_groups.items():
        if len(members) >= 3:
            patterns.append({"type": "星群", "scope": "house", "house": h, "planets": members})
    for s, members in sign_groups.items():
        if len(members) >= 3:
            patterns.append({
                "type": "星群", "scope": "sign", "sign": SIGNS_ZH[s],
                "signIndex": s, "planets": members,
            })

    def _pair_aspect(a: str, b: str):
        res = _aspect_between(planets[a]["longitude"], planets[b]["longitude"])
        return res[0] if res else None

    # 大三角：三颗行星两两三分相
    for trio in combinations(names, 3):
        kinds = [_pair_aspect(a, b) for a, b in combinations(trio, 2)]
        if kinds.count("trine") == 3:
            patterns.append({"type": "大三角", "planets": list(trio)})

    # T 三角：两刑 + 一冲，apex = 同时参与两个刑相的行星
    for trio in combinations(names, 3):
        rel = {pair: _pair_aspect(*pair) for pair in combinations(trio, 2)}
        squares = [p for p, k in rel.items() if k == "square"]
        if len(squares) == 2 and list(rel.values()).count("opposition") == 1:
            apex = set(squares[0]) & set(squares[1])
            if apex:
                patterns.append({"type": "T三角", "planets": list(trio), "apex": apex.pop()})

    # 大十字：四颗行星，四刑 + 两冲
    for quad in combinations(names, 4):
        kinds = [_pair_aspect(a, b) for a, b in combinations(quad, 2)]
        if kinds.count("square") == 4 and kinds.count("opposition") == 2:
            patterns.append({"type": "大十字", "planets": list(quad)})

    return patterns


def calculate_chart(
    birth_date: str,
    birth_time: str,
    city: str = "",
    latitude: float | None = None,
    longitude: float | None = None,
    timezone: str = "",
    house_system: str = "placidus",
    zodiac: str = "tropical",
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
        birth_text: 自由文本输入（如 "1994-05-20 14:30 北京"），供工作流直接传用户消息
        ephemeris_path: 历书数据目录（默认 app/tools/data/ephe/）

    Returns:
        排盘结果 dict，结构见 SCHEMA 出参说明。

    Raises:
        ValueError: 输入校验失败（缺时间、城市不在库、缺时区等）
    """
    # ── 1. 输入解析与校验 ──
    if birth_text:
        birth_date, birth_time, city = _parse_birth_text(birth_text)
        latitude, longitude, timezone = None, None, ""
    if not birth_date or not birth_time:
        raise ValueError("缺少出生日期或时间。请提供出生日期（YYYY-MM-DD）与时间（HH:MM）。")

    m = re.fullmatch(r"(\d{4})-(\d{2})-(\d{2})", birth_date)
    if not m:
        raise ValueError("出生日期格式错误，应为 YYYY-MM-DD。")
    year, month, day = int(m.group(1)), int(m.group(2)), int(m.group(3))
    if not (1800 <= year <= 2399):
        raise ValueError("出生年份超出历书覆盖范围（1800-2399）。")

    tm = re.fullmatch(r"(\d{1,2}):(\d{2})", birth_time)
    if not tm:
        raise ValueError("出生时间格式错误，应为 HH:MM。")
    hour, minute = int(tm.group(1)), int(tm.group(2))
    if not (0 <= hour <= 23 and 0 <= minute <= 59):
        raise ValueError("出生时间非法（小时 0-23，分钟 0-59）。")

    house_system = (house_system or "placidus").lower()
    zodiac = (zodiac or "tropical").lower()
    if house_system not in ("placidus", "whole_sign"):
        raise ValueError("宫位制仅支持 placidus 或 whole_sign。")
    if zodiac not in ("tropical", "sidereal"):
        raise ValueError("黄道类型仅支持 tropical 或 sidereal。")

    lat, lon, tz_name = _resolve_location(city, latitude, longitude, timezone)
    try:
        tz = ZoneInfo(tz_name)
    except ZoneInfoNotFoundError as exc:
        raise ValueError(f"无效的 IANA 时区: {tz_name}") from exc

    # ── 2. 当地时 → UTC → 儒略日 ──
    local_dt = datetime(year, month, day, hour, minute, tzinfo=tz)
    utc_dt = local_dt.astimezone(ZoneInfo("UTC"))
    utc_hour = utc_dt.hour + utc_dt.minute / 60.0

    swe = _swe()
    swe.set_ephe_path(ephemeris_path)
    flags = swe.FLG_SWIEPH
    ayanamsa = None
    if zodiac == "sidereal":
        swe.set_sid_mode(swe.SIDM_LAHIRI)
        flags |= swe.FLG_SIDEREAL
        ayanamsa = "Lahiri"
    jd = swe.julday(utc_dt.year, utc_dt.month, utc_dt.day, utc_hour)

    # ── 3. 十大星体 ──
    planets: dict[str, dict] = {}
    for name, pid in PLANET_IDS.items():
        xx, _ret = swe.calc_ut(jd, pid, flags)
        plon = xx[0] % 360
        planets[name] = {
            "sign": SIGNS_ZH[int(plon // 30) % 12],
            "signIndex": int(plon // 30) % 12,
            "degree": round(plon % 30, 4),
            "longitude": round(plon, 4),
            "retrograde": bool(xx[3] < 0),
        }

    # ── 4. 四轴与宫位（Placidus，高纬度自动降级整宫制） ──
    fallback = False
    house_code = b"W" if house_system == "whole_sign" else b"P"
    try:
        cusps, ascmc = swe.houses(jd, lat, lon, house_code)
        cusps = [c % 360 for c in cusps]
        # 校验无效宫头：NaN 或重复值（高纬度 Placidus 常见失败形态）
        if any(c != c for c in cusps) or len({round(c, 4) for c in cusps}) < 12:
            raise ValueError("invalid cusps")
    except Exception:
        if house_system == "whole_sign":
            raise ValueError("整宫制计算失败，请检查输入。")
        cusps, ascmc = swe.houses(jd, lat, lon, b"W")
        cusps = [c % 360 for c in cusps]
        fallback = True
        house_system = "whole_sign"

    asc_lon = ascmc[0] % 360
    mc_lon = ascmc[1] % 360
    angles = {
        "ascendant": _angle_point(asc_lon),
        "midheaven": _angle_point(mc_lon),
        "descendant": _angle_point((asc_lon + 180) % 360),
        "imum_coeli": _angle_point((mc_lon + 180) % 360),
    }

    houses: dict[str, dict] = {}
    for i in range(12):
        cusp = cusps[i]
        houses[str(i + 1)] = {
            "cusp": round(cusp, 4),
            "sign": SIGNS_ZH[int(cusp // 30) % 12],
            "planets": [],
        }
    if house_system == "whole_sign":
        asc_sign = int(asc_lon // 30) % 12
        for pname, pdata in planets.items():
            h = (pdata["signIndex"] - asc_sign) % 12 + 1
            houses[str(h)]["planets"].append(pname)
    else:
        for pname, pdata in planets.items():
            plon = pdata["longitude"]
            for i in range(12):
                start = cusps[i]
                end = cusps[(i + 1) % 12]
                if (plon - start) % 360 < (end - start) % 360:
                    houses[str(i + 1)]["planets"].append(pname)
                    break
    for pname, pdata in planets.items():
        for h, hdata in houses.items():
            if pname in hdata["planets"]:
                pdata["house"] = int(h)
                break

    # ── 5. 相位与格局 ──
    aspects: list[dict] = []
    for a, b in combinations(list(PLANET_IDS), 2):
        res = _aspect_between(planets[a]["longitude"], planets[b]["longitude"])
        if res:
            key, orb = res
            aspects.append({
                "p1": a, "p2": b,
                "type": ASPECT_TYPES_ZH[key], "typeEn": key, "orb": orb,
            })
    patterns = _find_patterns(planets)

    return {
        "meta": {
            "zodiac": zodiac,
            "houseSystem": house_system,
            "houseSystemFallback": fallback,
            "timezone": tz_name,
            "ephemeris": "pyswisseph",
            "ayanamsa": ayanamsa,
            "birthDateTime": local_dt.isoformat(),
            "utDateTime": utc_dt.strftime("%Y-%m-%dT%H:%M:%SZ"),
        },
        **angles,
        "planets": planets,
        "houses": houses,
        "aspects": aspects,
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
        "输出十大星体位置、四轴、十二宫位、相位、格局等结构化数据。"
        "口径：回归黄道(Tropical) + 地心(Geocentric) + Placidus 宫位制（默认）。"
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
            "description": "宫位制：placidus（默认，Placidus 宫位制）或 whole_sign（整宫制）",
            "required": False,
        },
        "zodiac": {
            "type": "string",
            "description": "黄道类型：tropical（默认，回归黄道）或 sidereal（恒星黄道，需指定 Ayanamsa）",
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
      "retrograde": false              // 是否逆行
    },
    "moon":     { "sign": "双子座", "signIndex": 2, "house": 10, "degree": 3.8,  "longitude": 63.8,  "retrograde": false },
    "mercury":  { "sign": "双子座", "signIndex": 2, "house": 10, "degree": 15.2, "longitude": 75.2,  "retrograde": false },
    "venus":    { "sign": "白羊座", "signIndex": 0, "house": 8,  "degree": 5.1,  "longitude": 5.1,   "retrograde": false },
    "mars":     { "sign": "白羊座", "signIndex": 0, "house": 7,  "degree": 28.3, "longitude": 28.3,  "retrograde": false },
    "jupiter":  { "sign": "天蝎座", "signIndex": 7, "house": 2,  "degree": 10.5, "longitude": 220.5, "retrograde": true  },
    "saturn":   { "sign": "双鱼座", "signIndex": 11,"house": 5,  "degree": 18.7, "longitude": 348.7, "retrograde": false },
    "uranus":   { "sign": "摩羯座", "signIndex": 9, "house": 3,  "degree": 22.1, "longitude": 292.1, "retrograde": false },
    "neptune":  { "sign": "摩羯座", "signIndex": 9, "house": 3,  "degree": 22.4, "longitude": 292.4, "retrograde": false },
    "pluto":    { "sign": "射手座", "signIndex": 8, "house": 2,  "degree": 27.5, "longitude": 267.5, "retrograde": true  }
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
    { "p1": "sun", "p2": "moon",     "type": "三分相", "typeEn": "trine",       "orb": 4.4 },
    { "p1": "sun", "p2": "saturn",   "type": "四分相", "typeEn": "square",       "orb": 1.9 },
    { "p1": "moon","p2": "mercury",  "type": "合相",   "typeEn": "conjunction",  "orb": 3.6 }
  ],

  "patterns": [
    { "type": "星群", "scope": "house", "house": 10, "planets": ["moon", "mercury"] },
    { "type": "T三角", "scope": "aspect", "planets": ["sun", "saturn", "moon"], "apex": "saturn" }
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
