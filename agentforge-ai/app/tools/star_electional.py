"""Electional Chart Tool：择时（Electional）——按启发式相位评分挑选吉日。

V2 扩展（《星盘分析扩展规划》1 节，依赖行运能力）：
- 输入：起始日期 + 天数（默认 7，上限 60）+ 可选本命盘（个人择时）
- 口径：对每个候选日（当地 hour 时采样）计算行运行星，
  按与本命盘（或快速行星内部）相位给出启发式评分并排序
- 输出：Top 候选日期（评分 + 利好/利空相位摘要）+ 最佳日期

评分启发式（确定性，非"标准答案"）：
  和谐相位（拱/六合）+1，紧张相位（刑/冲）-1，合相 0；
  快速行星（日月水金火）权重 1.0、慢速行星（木土天海冥）权重 0.5；
  与本命太阳/月亮/上升的相位权重 2.0，其余行星 1.0。
"""
import json
from datetime import date, timedelta
from itertools import combinations

from app.tools.star_base import (
    EPHE_PATH,
    aspect_info,
    build_ephemeris,
    julday,
    local_dt_to_utc,
    planets_at_jd,
    validate_date_time,
)
from app.tools.star_chart import calculate_chart

FAST_PLANETS = ["sun", "moon", "mercury", "venus", "mars"]
SLOW_PLANETS = ["jupiter", "saturn", "uranus", "neptune", "pluto"]

PLANET_ZH = {
    "sun": "太阳", "moon": "月亮", "mercury": "水星", "venus": "金星", "mars": "火星",
    "jupiter": "木星", "saturn": "土星", "uranus": "天王星", "neptune": "海王星", "pluto": "冥王星",
}
ANGLE_ZH = {"ascendant": "上升点", "midheaven": "天顶", "descendant": "下降点", "imum_coeli": "天底"}
ASPECT_ZH = {
    "conjunction": "合相", "opposition": "对分相", "trine": "三分相",
    "square": "四分相", "sextile": "六分相", "semi_sextile": "半六合",
    "semi_square": "半刑", "quintile": "五分相", "sesquiquadrate": "补八分相",
    "biquintile": "倍五分相", "quincunx": "梅花相",
}


def _target_label(name: str) -> str:
    return ANGLE_ZH.get(name) or PLANET_ZH.get(name, name)


def _score_day(
    transit_planets: dict,
    natal: dict | None,
    aspect_types: list[str] | None,
    orb_mode: str,
    custom_orbs: dict | None,
) -> tuple[float, list[dict], list[dict]]:
    """对单个候选日的行运相位打分，返回 (score, favorable, unfavorable)。"""
    score = 0.0
    favorable: list[dict] = []
    unfavorable: list[dict] = []

    def _add(tname: str, nname: str, key: str, orb: float, t_weight: float, n_weight: float):
        nonlocal score
        if key in ("trine", "sextile"):
            val = 1.0
        elif key in ("square", "opposition"):
            val = -1.0
        else:
            val = 0.0
        if not val:
            return
        score += val * t_weight * n_weight
        entry = {"transit": tname, "target": nname, "type": key, "orb": orb}
        (favorable if val > 0 else unfavorable).append(entry)

    if natal:
        targets = {name: p["longitude"] for name, p in natal["planets"].items()}
        targets["ascendant"] = natal["ascendant"]["longitude"]
        targets["midheaven"] = natal["midheaven"]["longitude"]
        for tname, tdata in transit_planets.items():
            t_weight = 1.0 if tname in FAST_PLANETS else 0.5
            for nname, nlon in targets.items():
                info = aspect_info(
                    tdata["longitude"], nlon,
                    aspect_keys=aspect_types,
                    orb_mode=orb_mode,
                    custom_orbs=custom_orbs,
                )
                if not info:
                    continue
                key, orb = info["typeEn"], info["orb"]
                n_weight = 2.0 if nname in ("sun", "moon", "ascendant") else 1.0
                _add(tname, nname, key, orb, t_weight, n_weight)
    else:
        # 无本命盘：仅快速行星内部相位（日月水金火）
        for a, b in combinations(FAST_PLANETS, 2):
            info = aspect_info(
                transit_planets[a]["longitude"], transit_planets[b]["longitude"],
                aspect_keys=aspect_types,
                orb_mode=orb_mode,
                custom_orbs=custom_orbs,
            )
            if not info:
                continue
            key, orb = info["typeEn"], info["orb"]
            _add(a, b, key, orb, 1.0, 1.0)

    score = round(score, 1)
    # 去重（同一对相位只保留一次，且只保留前 6 条）
    seen = set()
    for lst in (favorable, unfavorable):
        deduped = []
        for e in lst:
            pair = (e["transit"], e["target"], e["type"])
            if pair in seen:
                continue
            seen.add(pair)
            deduped.append(e)
        lst[:] = deduped[:6]
    return score, favorable, unfavorable


def _summary(favorable: list[dict], unfavorable: list[dict]) -> str:
    parts = []
    for e in favorable[:4]:
        parts.append(
            f"利好 {PLANET_ZH[e['transit']]} {ASPECT_ZH[e['type']]} {_target_label(e['target'])}（{e['orb']}°）"
        )
    for e in unfavorable[:4]:
        parts.append(
            f"利空 {PLANET_ZH[e['transit']]} {ASPECT_ZH[e['type']]} {_target_label(e['target'])}（{e['orb']}°）"
        )
    return "；".join(parts) if parts else "无明显显著相位"


def calculate_electional(
    start_date: str,
    days: int = 7,
    timezone: str = "Asia/Shanghai",
    purpose: str = "",
    hour: int = 12,
    birth_date: str = "",
    birth_time: str = "",
    city: str = "",
    latitude: float | None = None,
    longitude: float | None = None,
    birth_timezone: str = "",
    house_system: str = "placidus",
    zodiac: str = "tropical",
    ayanamsa: str = "lahiri",
    orb_mode: str = "modern",
    aspect_types: list[str] | None = None,
    custom_orbs: dict | None = None,
    birth_text: str = "",
    ephemeris_path: str = EPHE_PATH,
) -> dict:
    """择时计算核心函数（按日粗筛启发式评分）。

    Returns:
        择时结果 dict：meta + heuristics + candidates（Top 5）+ bestDate。
    """
    if not 1 <= int(days) <= 60:
        raise ValueError("天数需在 1-60 之间。")
    year, month, day, _h, _m = validate_date_time(start_date, "00:00")
    start = date(year, month, day)
    if not 0 <= int(hour) <= 23:
        raise ValueError("采样小时需在 0-23 之间。")
    sample_hour = int(hour)

    natal = None
    has_natal_input = bool(birth_text) or bool(birth_date and birth_time)
    if has_natal_input:
        natal = calculate_chart(
            birth_date=birth_date,
            birth_time=birth_time,
            city=city,
            latitude=latitude,
            longitude=longitude,
            timezone=birth_timezone,
            house_system=house_system,
            zodiac=zodiac,
            ayanamsa=ayanamsa,
            orb_mode=orb_mode,
            aspects=aspect_types,
            custom_orbs=custom_orbs,
            birth_text=birth_text,
            ephemeris_path=ephemeris_path,
        )
    else:
        zodiac = (zodiac or "tropical").lower()
        if zodiac not in ("tropical", "sidereal"):
            raise ValueError("黄道类型仅支持 tropical 或 sidereal。")

    swe, flags, ayanamsa = build_ephemeris(zodiac, ephemeris_path)
    candidates: list[dict] = []
    for i in range(int(days)):
        d = start + timedelta(days=i)
        _local_dt, utc_dt = local_dt_to_utc(d.year, d.month, d.day, sample_hour, 0, timezone)
        jd = julday(swe, utc_dt)
        transit = planets_at_jd(swe, jd, flags)
        score, favorable, unfavorable = _score_day(
            transit, natal, aspect_types, orb_mode, custom_orbs
        )
        candidates.append({
            "date": d.isoformat(),
            "score": score,
            "summary": _summary(favorable, unfavorable),
            "favorable": favorable,
            "unfavorable": unfavorable,
        })

    candidates.sort(key=lambda c: (-c["score"], c["date"]))
    top = candidates[:5]
    meta = {
        "zodiac": zodiac,
        "ephemeris": "pyswisseph",
        "ayanamsa": ayanamsa,
        "startDate": start.isoformat(),
        "days": int(days),
        "timezone": timezone,
        "sampleHour": sample_hour,
        "purpose": purpose or None,
        "hasNatal": natal is not None,
    }
    return {
        "meta": meta,
        "heuristics": (
            f"按日粗筛：每个候选日在当地 {sample_hour} 时采样行运行星；"
            "拱/六合 +1、刑/冲 -1、合相 0；快速行星（日月水金火）权重 1.0、"
            "慢速行星权重 0.5；与本命太阳/月亮/上升的相位权重 2.0。"
            "仅供参考，择时并非'标准答案'。"
        ),
        "candidates": top,
        "bestDate": top[0]["date"] if top else None,
    }


def run(payload: dict, config: dict | None = None) -> str:
    """工具注册表调用入口：返回 JSON 字符串或错误文本。"""
    config = config or {}
    try:
        result = calculate_electional(
            start_date=payload.get("startDate", ""),
            days=payload.get("days", 7),
            timezone=payload.get("timezone", "Asia/Shanghai"),
            purpose=payload.get("purpose", ""),
            hour=payload.get("hour", 12),
            birth_date=payload.get("birthDate", ""),
            birth_time=payload.get("birthTime", ""),
            city=payload.get("city", ""),
            latitude=payload.get("latitude"),
            longitude=payload.get("longitude"),
            birth_timezone=payload.get("birthTimezone", ""),
            house_system=config.get("default_house_system") or payload.get("houseSystem", "") or "placidus",
            zodiac=config.get("default_zodiac") or payload.get("zodiac", "") or "tropical",
            ayanamsa=config.get("default_ayanamsa") or payload.get("ayanamsa", "") or "lahiri",
            orb_mode=config.get("default_orb_mode") or payload.get("orbMode", "") or "modern",
            aspect_types=payload.get("aspects"),
            custom_orbs=payload.get("customOrbs"),
            birth_text=payload.get("birthText", ""),
            ephemeris_path=config.get("ephemeris_path") or EPHE_PATH,
        )
        return json.dumps(result, ensure_ascii=False)
    except ValueError as exc:
        return f"[electional_chart] 错误：{exc}"


SCHEMA = {
    "name": "electional_chart",
    "description": (
        "择时计算工具（V2）。输入起始日期与搜索天数（可选本命盘做个人择时），"
        "按启发式相位评分输出 Top 候选吉日（含利好/利空相位摘要），用于'选日子'场景"
        "（签约/搬家/出行/开始项目等）。仅供参考，非'标准答案'。"
    ),
    "parameters": {
        "startDate": {
            "type": "string",
            "description": "择时起始日期，格式 YYYY-MM-DD，如 2026-08-06",
        },
        "days": {
            "type": "number",
            "description": "搜索天数（1-60），默认 7",
            "required": False,
        },
        "timezone": {
            "type": "string",
            "description": "择时所在地 IANA 时区，默认 Asia/Shanghai",
            "required": False,
        },
        "purpose": {
            "type": "string",
            "description": "择时用途（如 签约/搬家/出行），透传给 LLM 解读，不参与计算",
            "required": False,
        },
        "hour": {
            "type": "number",
            "description": "每日采样小时（0-23），默认 12（当地正午）",
            "required": False,
        },
        "birthDate": {
            "type": "string",
            "description": "本命盘出生日期（可选，个人择时时使用），格式 YYYY-MM-DD",
            "required": False,
        },
        "birthTime": {
            "type": "string",
            "description": "本命盘出生时间（可选），格式 HH:MM",
            "required": False,
        },
        "city": {
            "type": "string",
            "description": "本命盘出生城市名（可选）。城市在库时自动推断经纬度与时区",
            "required": False,
        },
        "latitude": {
            "type": "number",
            "description": "本命盘纬度（可选）。城市不在库时使用",
            "required": False,
        },
        "longitude": {
            "type": "number",
            "description": "本命盘经度（可选）。城市不在库时使用",
            "required": False,
        },
        "birthTimezone": {
            "type": "string",
            "description": "本命盘出生地 IANA 时区名（可选）。使用经纬度输入时必填",
            "required": False,
        },
        "birthText": {
            "type": "string",
            "description": "本命盘自由文本输入（可选，如 '1994-05-20 14:30 北京'）",
            "required": False,
        },
        "houseSystem": {
            "type": "string",
            "description": "本命盘宫位制：placidus（默认）/ whole_sign / equal / koch / regiomontanus / campanus / porphyry / topocentric / alcabitius / morinus",
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
            "description": "评分采用的相位类型（缺省仅五大主相位）",
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
electional_chart 工具出参 JSON 结构定义
=======================================

成功时返回 JSON 字符串：

{
  "meta": {
    "zodiac": "tropical", "ephemeris": "pyswisseph", "ayanamsa": null,
    "startDate": "2026-08-06", "days": 7, "timezone": "Asia/Shanghai",
    "sampleHour": 12, "purpose": "签约", "hasNatal": true
  },
  "heuristics": "按日粗筛：……",
  "candidates": [  // 按评分降序，Top 5
    {
      "date": "2026-08-08",
      "score": 3.0,
      "summary": "利好 木星 三分相 太阳（0.8°）；利空 火星 四分相 月亮（2.1°）",
      "favorable": [ { "transit": "jupiter", "target": "sun", "type": "trine", "orb": 0.8 } ],
      "unfavorable": [ { "transit": "mars", "target": "moon", "type": "square", "orb": 2.1 } ]
    }
  ],
  "bestDate": "2026-08-08"
}

说明：type 为相位英文键；target 为本命行星键或 ascendant/midheaven。
错误时返回纯文本："[electional_chart] 错误：<错误说明>"。
"""
