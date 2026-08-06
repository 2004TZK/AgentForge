"""星盘计算共享基础（V3 增强版：行运/推运/合盘/择时复用）。

从 star_chart 抽出的公共能力：
- 城市库 / 经纬度 / IANA 时区解析（含中国历史夏令时）
- 出生信息自由文本解析（birthText）
- 瑞士星历表延迟加载与黄道模式（Tropical/Sidereal，多 Ayanamsa）
- 行星位置 / 虚点（南北交、福点、莉莉丝、宿命点、凯龙、小行星）/ 四轴与宫位
- 宫位制：Placidus（默认）/ 整宫 / 等宫 / Koch / Regiomontanus / Campanus /
  Porphyry / Topocentric / Alcabitius / Morinus（高纬度自动降级整宫制）
- 相位：五大主相位 + 六种次要相位，现代统一容许度 / 古典按星体容许度，
  支持入相/出相（applying/separating）判定
- 格局：大三角 / T 三角 / 大十字 / 星群 / 风筝 / 神秘长方形 / 上帝之指 /
  摇篮 / 大六分相 / 双 Yod + 分布格局（束型 / 碗型 / 桶型 / 火车头 / 跷跷板 /
  撒型 / 扇型）

口径与 V1 一致：Tropical + Geocentric + Placidus（默认），
可切换整宫制 / 恒星黄道；历书覆盖 1800-2399。
"""
import json
import math
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

# 五大主相位
MAJOR_ASPECTS = ("conjunction", "sextile", "square", "trine", "opposition")

# 次要相位（需显式开启）
MINOR_ASPECTS = (
    "semi_sextile",
    "semi_square",
    "quintile",
    "sesquiquadrate",
    "biquintile",
    "quincunx",
)

ALL_ASPECTS = MAJOR_ASPECTS + MINOR_ASPECTS

# 默认相位容许度（度）——现代统一流派：主相位 8/8/8/8/6，次要相位 2
DEFAULT_ORBS = {
    "conjunction": 8.0,   # 合相
    "opposition": 8.0,    # 对分相
    "trine": 8.0,         # 三分相
    "square": 8.0,        # 四分相
    "sextile": 6.0,       # 六分相
    "semi_sextile": 2.0,  # 半六合
    "semi_square": 2.0,   # 半刑
    "quintile": 2.0,      # 五分相
    "sesquiquadrate": 2.0,  # 补八分相
    "biquintile": 2.0,    # 倍五分相
    "quincunx": 2.0,      # 梅花相
}

# 古典占星按星体赋予的"星光范围"（度）；两星相位容许度 = 各自取一半相加
CLASSICAL_PLANET_ORBS = {
    "sun": 15.0,
    "moon": 12.0,
    "mercury": 7.0,
    "venus": 7.0,
    "mars": 8.0,
    "jupiter": 9.0,
    "saturn": 9.0,
    "uranus": 5.0,
    "neptune": 5.0,
    "pluto": 5.0,
}
# 虚点 / 四轴 / 小行星统一按 5°（古典参考标准）
CLASSICAL_POINT_ORB = 5.0

# 十大星体 pyswisseph 常量映射
PLANET_IDS = {
    "sun": 0, "moon": 1, "mercury": 2, "venus": 3, "mars": 4,
    "jupiter": 5, "saturn": 6, "uranus": 7, "neptune": 8, "pluto": 9,
}

# 虚点 / 小行星 pyswisseph 常量映射（swe.calc_ut 星体编号）
POINT_IDS = {
    "north_node": 10,     # 北交点（均值节点）
    "true_node": 11,      # 北交点（真节点）
    "lilith": 12,         # 莉莉丝（黑月，均值远地点）
    "true_lilith": 13,    # 真莉莉丝（摆动远地点）
    "chiron": 15,         # 凯龙星
    "ceres": 17,          # 谷神星
    "pallas": 18,         # 智神星
    "juno": 19,           # 婚神星
    "vesta": 20,          # 灶神星
}

# 派生虚点（不直接调用 swe.calc_ut）
DERIVED_POINTS = ("south_node", "true_south_node", "part_of_fortune", "vertex")

# 默认开启的虚点（主流入门配置：10 行星 + 四轴 + 南北交）
DEFAULT_POINTS = ["north_node", "south_node"]

POINT_ZH = {
    "north_node": "北交点",
    "south_node": "南交点",
    "true_node": "真北交点",
    "true_south_node": "真南交点",
    "lilith": "莉莉丝",
    "true_lilith": "真莉莉丝",
    "part_of_fortune": "福点",
    "vertex": "宿命点",
    "chiron": "凯龙星",
    "ceres": "谷神星",
    "pallas": "智神星",
    "juno": "婚神星",
    "vesta": "灶神星",
}

# 相位角度（度）
ASPECT_ANGLES = {
    "conjunction": 0.0,
    "semi_sextile": 30.0,
    "semi_square": 45.0,
    "sextile": 60.0,
    "quintile": 72.0,
    "square": 90.0,
    "trine": 120.0,
    "sesquiquadrate": 135.0,
    "biquintile": 144.0,
    "quincunx": 150.0,
    "opposition": 180.0,
}

# 黄道十二宫中文名（索引 0 = 白羊座）
SIGNS_ZH = [
    "白羊座", "金牛座", "双子座", "巨蟹座", "狮子座", "处女座",
    "天秤座", "天蝎座", "射手座", "摩羯座", "水瓶座", "双鱼座",
]

# 相位中文名
ASPECT_TYPES_ZH = {
    "conjunction": "合相",
    "semi_sextile": "半六合",
    "semi_square": "半刑",
    "sextile": "六分相",
    "quintile": "五分相",
    "square": "四分相",
    "trine": "三分相",
    "sesquiquadrate": "补八分相",
    "biquintile": "倍五分相",
    "quincunx": "梅花相",
    "opposition": "对分相",
}

# 四轴名称
ANGLES = ["ascendant", "midheaven", "descendant", "imum_coeli"]

# 宫位制 → pyswisseph house 代码
HOUSE_SYSTEMS = {
    "placidus": b"P",       # 普拉西德（时间分宫，现代主流）
    "whole_sign": b"W",     # 整宫制（一星座 = 一宫，古典/吠陀）
    "equal": b"E",          # 等宫制（从上升度数起每 30° 一宫）
    "koch": b"K",           # Koch（德式）
    "regiomontanus": b"R",  # Regiomontanus（文艺复兴）
    "campanus": b"C",       # Campanus（空间分宫）
    "porphyry": b"O",       # Porphyry（象限三等分）
    "topocentric": b"T",    # Topocentric / Polich-Page
    "alcabitius": b"B",     # Alcabitius（阿拉伯传统）
    "morinus": b"M",        # Morinus（赤道等分投影）
}

HOUSE_SYSTEMS_ZH = {
    "placidus": "Placidus",
    "whole_sign": "整宫制",
    "equal": "等宫制",
    "koch": "Koch",
    "regiomontanus": "Regiomontanus",
    "campanus": "Campanus",
    "porphyry": "Porphyry",
    "topocentric": "Topocentric",
    "alcabitius": "Alcabitius",
    "morinus": "Morinus",
}

# 高纬度可能失效、需自动降级整宫制的时间分宫制
TIME_BASED_HOUSE_SYSTEMS = {"placidus", "koch", "alcabitius", "topocentric"}

# 恒星黄道 Ayanamsa 显示名
AYANAMSA_ZH = {
    "lahiri": "Lahiri",
    "raman": "Raman",
    "krishnamurti": "Krishnamurti",
    "fagan_bradley": "Fagan/Bradley",
    "deluce": "DeLuce",
    "ushashi": "Ushashi",
    "j2000": "J2000",
    "j1900": "J1900",
    "b1950": "B1950",
    "suryasiddhanta": "SuryaSiddhanta",
    "true_citra": "True Citra",
    "ss_revati": "SS Revati",
}

ORB_MODES = ("modern", "classical")

# 出生信息自由文本解析
_DATE_RE = re.compile(r"(\d{4})\s*[-/.年]\s*(\d{1,2})\s*[-/.月]\s*(\d{1,2})\s*日?")
_TIME_RE = re.compile(r"(\d{1,2})\s*[:点时]\s*(\d{1,2})\s*分?")


def load_cities() -> list[dict]:
    """加载城市库 JSON。"""
    with open(CITIES_PATH, encoding="utf-8") as f:
        return json.load(f)


def normalize_en(text: str) -> str:
    """英文名归一化：小写 + 去除重音（如 Ürümqi → urumqi）。"""
    return "".join(
        ch for ch in unicodedata.normalize("NFKD", text)
        if not unicodedata.combining(ch)
    ).lower().strip()


def lookup_city(name: str) -> dict | None:
    """按中文名或英文名查找城市，返回 {lat, lng, tz} 或 None。"""
    cities = load_cities()
    name_zh = name.strip()
    name_en = normalize_en(name)
    for c in cities:
        if c["zh"] == name_zh or normalize_en(c["en"]) == name_en:
            return {"lat": c["lat"], "lng": c["lng"], "tz": c["tz"]}
    return None


def get_swe():
    """延迟导入 pyswisseph；未安装时抛出可读 ValueError（不影响注册表/应用启动）。"""
    try:
        import swisseph as swe
    except ImportError as exc:
        raise ValueError(
            "pyswisseph 未安装，无法进行星盘计算。请执行 pip install pyswisseph tzdata"
        ) from exc
    return swe


def parse_birth_text(text: str) -> tuple[str, str, str]:
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


def resolve_location(
    city: str, latitude: float | None, longitude: float | None, timezone: str
) -> tuple[float, float, str]:
    """解析出生地点：city 优先（城市库推断经纬度+时区），否则用经纬度（必须带时区）。"""
    if city:
        loc = lookup_city(city)
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


def validate_date_time(birth_date: str, birth_time: str) -> tuple[int, int, int, int, int]:
    """校验出生日期/时间，返回 (year, month, day, hour, minute)。"""
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
    return year, month, day, hour, minute


def local_dt_to_utc(
    year: int, month: int, day: int, hour: int, minute: int, tz_name: str
) -> tuple[datetime, datetime]:
    """当地时 → (本地 datetime, UTC datetime)。时区使用 zoneinfo 历史规则。"""
    try:
        tz = ZoneInfo(tz_name)
    except ZoneInfoNotFoundError as exc:
        raise ValueError(f"无效的 IANA 时区: {tz_name}") from exc
    local_dt = datetime(year, month, day, hour, minute, tzinfo=tz)
    utc_dt = local_dt.astimezone(ZoneInfo("UTC"))
    return local_dt, utc_dt


def _ayanamsa_codes(swe) -> dict[str, int]:
    """swe 常量 → Ayanamsa 代码映射（延迟读取，避免模块导入期依赖 pyswisseph）。"""
    return {
        "lahiri": swe.SIDM_LAHIRI,
        "raman": swe.SIDM_RAMAN,
        "krishnamurti": swe.SIDM_KRISHNAMURTI,
        "fagan_bradley": swe.SIDM_FAGAN_BRADLEY,
        "deluce": swe.SIDM_DELUCE,
        "ushashi": swe.SIDM_USHASHASHI,
        "j2000": swe.SIDM_J2000,
        "j1900": swe.SIDM_J1900,
        "b1950": swe.SIDM_B1950,
        "suryasiddhanta": swe.SIDM_SURYASIDDHANTA,
        "true_citra": swe.SIDM_TRUE_CITRA,
        "ss_revati": swe.SIDM_SS_REVATI,
    }


def build_ephemeris(zodiac: str, ephemeris_path: str, ayanamsa: str = "lahiri") -> tuple:
    """构建历书上下文，返回 (swe, flags, ayanamsa_name)。

    zodiac: tropical | sidereal（sidereal 需指定 Ayanamsa，默认 Lahiri）。
    """
    swe = get_swe()
    swe.set_ephe_path(ephemeris_path)
    flags = swe.FLG_SWIEPH | swe.FLG_SPEED  # FLG_SPEED 使 calc_ut 返回速度（度/天）
    ayanamsa_name = None
    if zodiac == "sidereal":
        key = (ayanamsa or "lahiri").lower().replace("-", "_").replace(" ", "_")
        codes = _ayanamsa_codes(swe)
        if key not in codes:
            raise ValueError(
                f"不支持的 Ayanamsa: {ayanamsa}。支持：{'、'.join(sorted(codes))}"
            )
        swe.set_sid_mode(codes[key])
        flags |= swe.FLG_SIDEREAL
        ayanamsa_name = AYANAMSA_ZH[key]
    return swe, flags, ayanamsa_name


def julday(swe, utc_dt: datetime) -> float:
    """UTC datetime → 儒略日（UT，适合 swe.calc_ut / swe.houses）。"""
    utc_hour = utc_dt.hour + utc_dt.minute / 60.0
    return swe.julday(utc_dt.year, utc_dt.month, utc_dt.day, utc_hour)


def prepare_chart_inputs(
    *,
    birth_date: str,
    birth_time: str,
    city: str = "",
    latitude: float | None = None,
    longitude: float | None = None,
    timezone: str = "",
    house_system: str = "placidus",
    zodiac: str = "tropical",
    ayanamsa: str = "lahiri",
    birth_text: str = "",
    ephemeris_path: str = EPHE_PATH,
) -> dict:
    """解析并校验一组出生/行运输入，返回计算上下文 dict。

    Returns:
        {
          "lat", "lon", "tz_name", "local_dt", "utc_dt", "jd",
          "swe", "flags", "ayanamsa", "zodiac", "house_system",
        }
    """
    if birth_text:
        birth_date, birth_time, city = parse_birth_text(birth_text)
        latitude, longitude, timezone = None, None, ""
    year, month, day, hour, minute = validate_date_time(birth_date, birth_time)

    house_system = (house_system or "placidus").lower()
    zodiac = (zodiac or "tropical").lower()
    if house_system not in HOUSE_SYSTEMS:
        raise ValueError(f"宫位制仅支持 {'、'.join(HOUSE_SYSTEMS)}。")
    if zodiac not in ("tropical", "sidereal"):
        raise ValueError("黄道类型仅支持 tropical 或 sidereal。")

    lat, lon, tz_name = resolve_location(city, latitude, longitude, timezone)
    local_dt, utc_dt = local_dt_to_utc(year, month, day, hour, minute, tz_name)
    swe, flags, ayanamsa_name = build_ephemeris(zodiac, ephemeris_path, ayanamsa)
    jd = julday(swe, utc_dt)
    return {
        "lat": lat, "lon": lon, "tz_name": tz_name,
        "local_dt": local_dt, "utc_dt": utc_dt, "jd": jd,
        "swe": swe, "flags": flags, "ayanamsa": ayanamsa_name,
        "zodiac": zodiac, "house_system": house_system,
    }


def angle_point(longitude: float) -> dict:
    """黄经 → 点位结构（四轴/任意黄经）。"""
    lon = longitude % 360
    return {
        "sign": SIGNS_ZH[int(lon // 30) % 12],
        "signIndex": int(lon // 30) % 12,
        "degree": round(lon % 30, 4),
        "longitude": round(lon, 4),
    }


def resolve_aspect_keys(aspects: list[str] | None) -> tuple[str, ...]:
    """规范化相位开关：None → 仅五大主相位。"""
    if not aspects:
        return MAJOR_ASPECTS
    keys = tuple(k.lower() for k in aspects)
    invalid = [k for k in keys if k not in ASPECT_ANGLES]
    if invalid:
        raise ValueError(
            f"不支持的相位类型: {'、'.join(invalid)}。支持：{'、'.join(ALL_ASPECTS)}"
        )
    return keys


def planet_orb(name: str, orb_mode: str = "modern") -> float | None:
    """星体基础容许度。modern 返回 None（统一按相位给），classical 返回星光范围。"""
    if orb_mode == "classical":
        return CLASSICAL_PLANET_ORBS.get(name, CLASSICAL_POINT_ORB)
    return None


def aspect_orb(
    key: str,
    orb_a: float | None,
    orb_b: float | None,
    orb_mode: str = "modern",
    custom_orbs: dict | None = None,
) -> float:
    """计算某相位的容许度（度）。

    modern：按相位统一给（可被 custom_orbs 覆盖）。
    classical：两星各自星光范围取一半相加；刑/拱打 7.5 折、六合打 5 折，
    次要相位统一 1°（参考 Al-Biruni / Lilly / Alan Leo 传统标准）。
    """
    if custom_orbs and key in custom_orbs:
        return float(custom_orbs[key])
    if orb_mode == "classical":
        if key in MINOR_ASPECTS:
            return 1.0
        full = ((orb_a if orb_a is not None else CLASSICAL_POINT_ORB)
                + (orb_b if orb_b is not None else CLASSICAL_POINT_ORB)) / 2.0
        if key in ("square", "trine"):
            return full * 0.75
        if key == "sextile":
            return full * 0.5
        return full
    return DEFAULT_ORBS.get(key, 2.0)


def _aspect_direction(delta: float, target: float, rate: float) -> str | None:
    """判定入相/出相。

    delta 为带符号角距（-180~180），rate = speed_b - speed_a（度/天）。
    applying = 正在接近精确相位；separating = 已经离开精确相位。
    """
    if abs(abs(delta) - target) < 1e-6:
        return "exact"
    if rate == 0:
        return None
    if target == 0.0:
        return "applying" if (delta > 0) != (rate > 0) else "separating"
    if target == 180.0:
        return "applying" if (delta > 0) == (rate > 0) else "separating"
    lhs = math.copysign(1.0, target - abs(delta))
    rhs = math.copysign(1.0, delta) * math.copysign(1.0, rate)
    return "applying" if lhs == rhs else "separating"


def aspect_info(
    lon_a: float,
    lon_b: float,
    *,
    aspect_keys: list[str] | None = None,
    orb_mode: str = "modern",
    orb_a: float | None = None,
    orb_b: float | None = None,
    speed_a: float | None = None,
    speed_b: float | None = None,
    custom_orbs: dict | None = None,
) -> dict | None:
    """计算两黄经之间是否构成相位，返回 {typeEn, type, angle, orb, direction}。"""
    keys = resolve_aspect_keys(aspect_keys)
    diff = abs(lon_a - lon_b) % 360
    diff = min(diff, 360 - diff)
    best: tuple[float, str] | None = None
    for key in keys:
        orb = aspect_orb(key, orb_a, orb_b, orb_mode, custom_orbs)
        if abs(diff - ASPECT_ANGLES[key]) <= orb + 1e-9:
            gap = abs(diff - ASPECT_ANGLES[key])
            if best is None or gap < best[0]:
                best = (gap, key)
    if best is None:
        return None
    gap, key = best
    direction = None
    if speed_a is not None and speed_b is not None:
        delta = ((lon_b - lon_a + 180.0) % 360.0) - 180.0
        direction = _aspect_direction(delta, ASPECT_ANGLES[key], speed_b - speed_a)
    return {
        "typeEn": key,
        "type": ASPECT_TYPES_ZH[key],
        "angle": ASPECT_ANGLES[key],
        "orb": round(gap, 4),
        "direction": direction,
    }


def aspect_between(
    lon_a: float,
    lon_b: float,
    *,
    aspect_keys: list[str] | None = None,
    orb_mode: str = "modern",
    orb_a: float | None = None,
    orb_b: float | None = None,
    speed_a: float | None = None,
    speed_b: float | None = None,
    custom_orbs: dict | None = None,
) -> tuple[str, float] | None:
    """兼容旧接口：返回 (typeEn, orb) 或 None。"""
    info = aspect_info(
        lon_a, lon_b,
        aspect_keys=aspect_keys,
        orb_mode=orb_mode,
        orb_a=orb_a,
        orb_b=orb_b,
        speed_a=speed_a,
        speed_b=speed_b,
        custom_orbs=custom_orbs,
    )
    if info is None:
        return None
    return info["typeEn"], info["orb"]


def _pos_lon(value) -> float:
    return value if isinstance(value, (int, float)) else value["longitude"]


def _pos_speed(value) -> float | None:
    if isinstance(value, (int, float)):
        return None
    return value.get("speed")


def _pos_orb(value, orb_mode: str) -> float | None:
    if isinstance(value, (int, float)):
        return None
    return value.get("orb", planet_orb(str(value.get("name", "")), orb_mode))


def compute_aspects(
    positions: dict,
    *,
    aspect_keys: list[str] | None = None,
    orb_mode: str = "modern",
    custom_orbs: dict | None = None,
    include_direction: bool = True,
) -> list[dict]:
    """对一组位置两两计算相位。

    positions: {name: longitude | {"longitude": .., "speed": .., "orb": ..}}
    返回 [{p1, p2, type, typeEn, angle, orb, direction?}]。
    """
    aspects: list[dict] = []
    names = list(positions)
    for i in range(len(names)):
        for j in range(i + 1, len(names)):
            a, b = names[i], names[j]
            info = aspect_info(
                _pos_lon(positions[a]),
                _pos_lon(positions[b]),
                aspect_keys=aspect_keys,
                orb_mode=orb_mode,
                orb_a=_pos_orb(positions[a], orb_mode),
                orb_b=_pos_orb(positions[b], orb_mode),
                speed_a=_pos_speed(positions[a]),
                speed_b=_pos_speed(positions[b]),
                custom_orbs=custom_orbs,
            )
            if info is None:
                continue
            entry: dict = {
                "p1": a, "p2": b,
                "type": info["type"], "typeEn": info["typeEn"],
                "angle": info["angle"], "orb": info["orb"],
            }
            if include_direction and info["direction"]:
                entry["direction"] = info["direction"]
            aspects.append(entry)
    return aspects


def _pair_kind(
    planets: dict,
    a: str,
    b: str,
    aspect_keys: list[str] | None,
    orb_mode: str,
    custom_orbs: dict | None,
) -> str | None:
    res = aspect_between(
        planets[a]["longitude"],
        planets[b]["longitude"],
        aspect_keys=aspect_keys,
        orb_mode=orb_mode,
        orb_a=planet_orb(a, orb_mode),
        orb_b=planet_orb(b, orb_mode),
        custom_orbs=custom_orbs,
    )
    return res[0] if res else None


def _sorted_lons(planets: dict, names: list[str]) -> list[float]:
    return sorted(planets[n]["longitude"] % 360 for n in names)


def _distribution_patterns(planets: dict, names: list[str]) -> list[dict]:
    """全盘分布格局（启发式判定，按特异性优先级只命中一种）。"""
    if len(names) < 3:
        return []
    lons = _sorted_lons(planets, names)
    n = len(lons)
    gaps = [(lons[(i + 1) % n] - lons[i]) % 360 for i in range(n)]
    max_gap = max(gaps)
    span_all = 360.0 - max_gap
    result: list[dict] = []

    def _leading(gap_idx: int) -> str:
        """紧挨最大空缺区顺时针方向的第一颗行星 = 领头/边缘星。"""
        lon = lons[(gap_idx + 1) % n]
        for name in names:
            if abs((planets[name]["longitude"] % 360) - lon) < 1e-9:
                return name
        return names[0]

    # 束型：全部行星集中在 ≤120° 弧段
    if span_all <= 120.0 + 1e-6:
        return [{"type": "束型", "planets": list(names), "span": round(span_all, 2)}]
    # 碗型：全部行星集中在 ≤180° 弧段（且非束型）
    if span_all <= 180.0 + 1e-6:
        gap_idx = gaps.index(max_gap)
        return [{
            "type": "碗型",
            "planets": list(names),
            "span": round(span_all, 2),
            "rim": _leading(gap_idx),
        }]
    # 桶型：9 颗在 ≤180° 弧段，1 颗孤立成"把手"
    for i in range(n):
        others = [lons[j] for j in range(n) if j != i]
        m = len(others)
        other_gaps = [(others[(k + 1) % m] - others[k]) % 360 for k in range(m)]
        if 360.0 - max(other_gaps) <= 180.0 + 1e-6:
            handle = next(
                name for name in names
                if abs((planets[name]["longitude"] % 360) - lons[i]) < 1e-9
            )
            return [{"type": "桶型", "planets": list(names), "handle": handle}]
    # 跷跷板：两组行星相对分布，两个明显空缺区
    order = sorted(range(n), key=lambda k: gaps[k], reverse=True)
    i1, i2 = order[0], order[1]
    if gaps[i1] >= 45.0 and gaps[i2] >= 45.0:
        start_a = (i1 + 1) % n
        start_b = (i2 + 1) % n
        count_a = (i2 - i1) % n
        count_b = n - count_a
        span_a = (lons[(start_a + count_a - 1) % n] - lons[start_a]) % 360
        span_b = (lons[(start_b + count_b - 1) % n] - lons[start_b]) % 360
        if count_a >= 3 and count_b >= 3 and span_a <= 150.0 and span_b <= 150.0:
            group_a = [lons[(start_a + k) % n] for k in range(count_a)]
            group_b = [lons[(start_b + k) % n] for k in range(count_b)]
            def _group_names(group_lons: list[float]) -> list[str]:
                out = []
                for name in names:
                    if any(
                        abs((planets[name]["longitude"] % 360) - gl) < 1e-9
                        for gl in group_lons
                    ):
                        out.append(name)
                return out
            return [{
                "type": "跷跷板型",
                "planets": list(names),
                "groupA": _group_names(group_a),
                "groupB": _group_names(group_b),
            }]
    # 火车头：行星集中在 ≤240° 弧段（剩余 ≥120° 空缺）
    if span_all <= 240.0 + 1e-6:
        gap_idx = gaps.index(max_gap)
        return [{
            "type": "火车头型",
            "planets": list(names),
            "span": round(span_all, 2),
            "leading": _leading(gap_idx),
        }]
    # 撒型：≥7 个星座、无明显大空缺
    signs = {int(planets[name]["longitude"] // 30) % 12 for name in names}
    if len(signs) >= 7:
        return [{
            "type": "撒型",
            "planets": list(names),
            "signs": len(signs),
        }]
    # 扇型：三组分散（三个 ≥30° 空缺），≥4 星座
    big = [g for g in gaps if g >= 30.0]
    signs2 = {int(planets[name]["longitude"] // 30) % 12 for name in names}
    if len(big) >= 3 and len(signs2) >= 4:
        return [{"type": "扇型", "planets": list(names), "clusters": len(big)}]
    return result


def find_patterns(
    planets: dict,
    *,
    aspect_keys: list[str] | None = None,
    orb_mode: str = "modern",
    custom_orbs: dict | None = None,
) -> list[dict]:
    """基于相位表判定格局：相位格局 + 星群 + 分布格局。"""
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

    def _kind(a: str, b: str) -> str | None:
        return _pair_kind(planets, a, b, aspect_keys, orb_mode, custom_orbs)

    # 大三角：三颗行星两两三分相
    grand_trines: list[tuple[str, str, str]] = []
    for trio in combinations(names, 3):
        kinds = [_kind(a, b) for a, b in combinations(trio, 2)]
        if kinds.count("trine") == 3:
            patterns.append({"type": "大三角", "planets": list(trio)})
            grand_trines.append(tuple(trio))

    # T 三角：两刑 + 一冲，apex = 同时参与两个刑相的行星
    for trio in combinations(names, 3):
        rel = {pair: _kind(*pair) for pair in combinations(trio, 2)}
        squares = [p for p, k in rel.items() if k == "square"]
        if len(squares) == 2 and list(rel.values()).count("opposition") == 1:
            apex = set(squares[0]) & set(squares[1])
            if apex:
                patterns.append({"type": "T三角", "planets": list(trio), "apex": apex.pop()})

    # 大十字：四颗行星，四刑 + 两冲
    for quad in combinations(names, 4):
        kinds = [_kind(a, b) for a, b in combinations(quad, 2)]
        if kinds.count("square") == 4 and kinds.count("opposition") == 2:
            patterns.append({"type": "大十字", "planets": list(quad)})

    # 风筝：大三角 + 一颗行星与大三角一点对分、与另两点六合
    for trio in grand_trines:
        for p in names:
            if p in trio:
                continue
            kinds = {m: _kind(p, m) for m in trio}
            opps = [m for m, k in kinds.items() if k == "opposition"]
            sexts = [m for m, k in kinds.items() if k == "sextile"]
            if len(opps) == 1 and len(sexts) == 2:
                patterns.append({
                    "type": "风筝",
                    "planets": list(trio) + [p],
                    "opposed": opps[0],
                    "apex": p,
                })

    # 神秘长方形：四颗行星，两冲 + 两拱 + 两六合
    for quad in combinations(names, 4):
        kinds = [_kind(a, b) for a, b in combinations(quad, 2)]
        if (kinds.count("opposition") == 2
                and kinds.count("trine") == 2
                and kinds.count("sextile") == 2):
            patterns.append({"type": "神秘长方形", "planets": list(quad)})

    # 上帝之指（Yod）：两梅花 + 一六合，apex = 双梅花星
    yods: list[tuple[str, str, str]] = []
    for trio in combinations(names, 3):
        rel = {pair: _kind(*pair) for pair in combinations(trio, 2)}
        quinc = [p for p, k in rel.items() if k == "quincunx"]
        if len(quinc) == 2 and list(rel.values()).count("sextile") == 1:
            apex = set(quinc[0]) & set(quinc[1])
            if apex:
                patterns.append({"type": "上帝之指", "planets": list(trio), "apex": apex.pop()})
                yods.append(tuple(trio))

    # 双 Yod：两组上帝之指共享至少一颗行星
    for i in range(len(yods)):
        for j in range(i + 1, len(yods)):
            if set(yods[i]) & set(yods[j]):
                patterns.append({
                    "type": "双Yod",
                    "planets": sorted(set(yods[i]) | set(yods[j])),
                })

    # 摇篮：四颗行星，两六合 + 两拱 + 一冲（剩一对无主相位）
    for quad in combinations(names, 4):
        kinds = [_kind(a, b) for a, b in combinations(quad, 2)]
        if (kinds.count("sextile") == 2
                and kinds.count("trine") == 2
                and kinds.count("opposition") == 1
                and kinds.count(None) == 1):
            patterns.append({"type": "摇篮", "planets": list(quad)})

    # 大六分相：六颗行星组成六合环（每颗恰有两个六合伙伴）且含 ≥2 组大三角
    for six in combinations(names, 6):
        sext_counts = {p: 0 for p in six}
        sext_total = 0
        trine_total = 0
        for a, b in combinations(six, 2):
            k = _kind(a, b)
            if k == "sextile":
                sext_counts[a] += 1
                sext_counts[b] += 1
                sext_total += 1
            elif k == "trine":
                trine_total += 1
        if (sext_total == 6
                and all(c == 2 for c in sext_counts.values())
                and trine_total >= 2):
            patterns.append({"type": "大六分相", "planets": list(six)})

    # 分布格局（全盘）
    dist = _distribution_patterns(planets, names)
    patterns.extend(dist)

    return patterns


def planets_at_jd(swe, jd: float, flags: int) -> dict[str, dict]:
    """计算指定儒略日（UT）的十大星体位置（含速度与逆行标记）。"""
    planets: dict[str, dict] = {}
    for name, pid in PLANET_IDS.items():
        xx, _ret = swe.calc_ut(jd, pid, flags)
        plon = xx[0] % 360
        speed = float(xx[3]) if len(xx) > 3 else 0.0
        planets[name] = {
            "sign": SIGNS_ZH[int(plon // 30) % 12],
            "signIndex": int(plon // 30) % 12,
            "degree": round(plon % 30, 4),
            "longitude": round(plon, 4),
            "speed": round(speed, 6),
            "retrograde": bool(speed < 0),
        }
    return planets


def points_at_jd(
    swe,
    jd: float,
    flags: int,
    *,
    asc_lon: float,
    sun_lon: float,
    moon_lon: float,
    vertex_lon: float | None = None,
    points: list[str] | None = None,
) -> dict[str, dict]:
    """计算请求的虚点/小行星位置（结构同行星，含 house 时由调用方回填）。"""
    requested = [p.lower() for p in (points or [])]
    out: dict[str, dict] = {}

    def _calc(pid: int):
        try:
            xx, ret = swe.calc_ut(jd, pid, flags)
        except Exception:  # noqa: BLE001 - 星历文件缺失等情形跳过该虚点
            return None
        # 非致命：星历文件缺失等情形下仍返回位置（Moshier 兜底），跳过明显失败
        if ret != 0 and abs(xx[0]) < 1e-9 and abs(xx[3]) < 1e-9:
            return None
        return xx

    def _base(plon: float, speed: float) -> dict:
        return {
            "sign": SIGNS_ZH[int(plon // 30) % 12],
            "signIndex": int(plon // 30) % 12,
            "degree": round(plon % 30, 4),
            "longitude": round(plon, 4),
            "speed": round(speed, 6) if speed is not None else None,
            "retrograde": bool(speed is not None and speed < 0),
        }

    node_cache: dict[int, tuple[float, float]] = {}
    node_family = {"north_node", "south_node", "true_node", "true_south_node"}
    for name in requested:
        if name in POINT_IDS:
            xx = _calc(POINT_IDS[name])
            if xx is None:
                continue
            out[name] = _base(xx[0] % 360, float(xx[3]) if len(xx) > 3 else 0.0)
            if name in node_family:
                out[name]["retrograde"] = True  # 交点始终逆行
        elif name in ("south_node", "true_south_node"):
            base_id = POINT_IDS["north_node"] if name == "south_node" else POINT_IDS["true_node"]
            if base_id not in node_cache:
                xx = _calc(base_id)
                if xx is None:
                    continue
                node_cache[base_id] = (xx[0] % 360, float(xx[3]) if len(xx) > 3 else 0.0)
            lon, speed = node_cache[base_id]
            out[name] = _base((lon + 180.0) % 360, speed)
        elif name == "part_of_fortune":
            # 昼生：ASC + 月 - 日；夜生：ASC + 日 - 月
            if ((sun_lon - asc_lon) % 360) < 180.0:
                plon = (asc_lon + moon_lon - sun_lon) % 360
            else:
                plon = (asc_lon + sun_lon - moon_lon) % 360
            out[name] = _base(plon, None)
        elif name == "vertex" and vertex_lon is not None:
            out[name] = _base(vertex_lon % 360, None)
    return out


def houses_and_angles(
    swe, jd: float, lat: float, lon: float, house_system: str
) -> tuple[dict, dict, str, bool, float, float, float]:
    """计算四轴与宫位（时间分宫制高纬度自动降级整宫制）。

    Returns:
        (houses, angles, effective_house_system, fallback, asc_lon, mc_lon, vertex_lon)
    """
    fallback = False
    requested = (house_system or "placidus").lower()
    if requested not in HOUSE_SYSTEMS:
        raise ValueError(f"宫位制仅支持 {'、'.join(HOUSE_SYSTEMS)}。")
    house_code = HOUSE_SYSTEMS[requested]
    try:
        cusps, ascmc = swe.houses(jd, lat, lon, house_code)
        cusps = [c % 360 for c in cusps]
        # 校验无效宫头：NaN 或重复值（高纬度时间分宫制常见失败形态）
        if any(c != c for c in cusps) or len({round(c, 4) for c in cusps}) < 12:  # noqa: PLR0124
            raise ValueError("invalid cusps")
    except Exception:  # noqa: BLE001 - 宫位计算失败统一走降级/报错路径
        if requested not in TIME_BASED_HOUSE_SYSTEMS:
            raise ValueError(f"{HOUSE_SYSTEMS_ZH[requested]} 宫位制计算失败，请检查输入。")
        cusps, ascmc = swe.houses(jd, lat, lon, b"W")
        cusps = [c % 360 for c in cusps]
        fallback = True
        house_system = "whole_sign"

    asc_lon = ascmc[0] % 360
    mc_lon = ascmc[1] % 360
    angles = {
        "ascendant": angle_point(asc_lon),
        "midheaven": angle_point(mc_lon),
        "descendant": angle_point((asc_lon + 180) % 360),
        "imum_coeli": angle_point((mc_lon + 180) % 360),
    }
    vertex_lon = (ascmc[3] % 360) if len(ascmc) > 3 else (asc_lon + 180.0) % 360

    houses: dict[str, dict] = {}
    for i in range(12):
        cusp = cusps[i]
        houses[str(i + 1)] = {
            "cusp": round(cusp, 4),
            "sign": SIGNS_ZH[int(cusp // 30) % 12],
            "planets": [],
        }
    return houses, angles, house_system, fallback, asc_lon, mc_lon, vertex_lon


def house_of_longitude(
    cusps: list[float], house_system: str, asc_lon: float, plon: float
) -> int:
    """按宫头黄经确定黄经所在宫位（1-12）。"""
    if house_system == "whole_sign":
        asc_sign = int(asc_lon // 30) % 12
        return int((int(plon // 30) % 12 - asc_sign) % 12) + 1
    for i in range(12):
        start = cusps[i]
        end = cusps[(i + 1) % 12]
        if (plon - start) % 360 < (end - start) % 360:
            return i + 1
    return 12


def assign_houses(
    planets: dict[str, dict], houses: dict[str, dict], house_system: str, asc_lon: float
) -> None:
    """将行星落入宫位并回填 planets[name]["house"] 与 houses[i]["planets"]。"""
    cusps = [houses[str(i + 1)]["cusp"] for i in range(12)]
    for pname, pdata in planets.items():
        h = house_of_longitude(cusps, house_system, asc_lon, pdata["longitude"])
        pdata["house"] = h
        houses[str(h)]["planets"].append(pname)


def assign_point_houses(
    points: dict[str, dict], houses: dict[str, dict], house_system: str, asc_lon: float
) -> None:
    """给虚点回填 house 字段（不写入宫位 planets 列表，保持行星列表纯净）。"""
    if not points:
        return
    cusps = [houses[str(i + 1)]["cusp"] for i in range(12)]
    for pdata in points.values():
        h = house_of_longitude(cusps, house_system, asc_lon, pdata["longitude"])
        pdata["house"] = h


def natal_chart_section(chart: dict) -> dict:
    """从 star_chart 完整结果中提取"本命盘"区块（供行运/推运/合盘组装出参）。"""
    return {
        "planets": chart["planets"],
        "houses": chart["houses"],
        "aspects": chart["aspects"],
        "patterns": chart["patterns"],
        "points": chart.get("points", {}),
        "ascendant": chart["ascendant"],
        "midheaven": chart["midheaven"],
        "descendant": chart["descendant"],
        "imum_coeli": chart["imum_coeli"],
    }
