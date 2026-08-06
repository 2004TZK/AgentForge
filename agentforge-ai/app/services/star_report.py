"""星盘报告导出（V2）：Markdown / PDF。

输入任意星盘工具结果（star_chart / transit_chart / progression_chart /
synastry_chart / electional_chart），输出结构化"分节"内容，
再序列化为 Markdown 文本或 reportlab PDF（CJK 内嵌字体 STSong-Light）。

免责声明与占星口径提示由各报告统一附带。
"""
from datetime import datetime

from app.tools.star_base import (
    ASPECT_TYPES_ZH,
    HOUSE_SYSTEMS_ZH,
    PLANET_IDS,
    POINT_ZH,
)

PLANET_ZH = {
    "sun": "太阳", "moon": "月亮", "mercury": "水星", "venus": "金星", "mars": "火星",
    "jupiter": "木星", "saturn": "土星", "uranus": "天王星", "neptune": "海王星", "pluto": "冥王星",
}
ANGLE_ZH = {
    "ascendant": "上升点 ASC",
    "midheaven": "天顶 MC",
    "descendant": "下降点 DES",
    "imum_coeli": "天底 IC",
}

DISCLAIMER = "以上内容仅供娱乐与自我探索参考，不作为任何决策依据。"


def _meta_line(chart: dict) -> str:
    meta = chart.get("meta", {})
    zodiac = "恒星黄道" if meta.get("zodiac") == "sidereal" else "回归黄道"
    if meta.get("ayanamsa"):
        zodiac += f"（{meta['ayanamsa']}）"
    house = HOUSE_SYSTEMS_ZH.get(meta.get("houseSystem", ""), meta.get("houseSystem") or "Placidus")
    fallback = "（高纬度自动降级整宫制）" if meta.get("houseSystemFallback") else ""
    orb = " · 古典容许度" if meta.get("orbMode") == "classical" else ""
    tz = meta.get("timezone", "")
    birth = meta.get("birthDateTime", "")
    return f"出生时间 {birth} · 时区 {tz} · {zodiac} · {house}{fallback}{orb}"


def _fmt_planet(chart: dict, name: str) -> str:
    p = chart["planets"].get(name)
    if not p:
        return PLANET_ZH.get(name, name)
    retro = " ℞" if p.get("retrograde") else ""
    return f"{PLANET_ZH.get(name, name)} {p['sign']} {p['degree']:.1f}° 第{p.get('house', '?')}宫{retro}"


def _aspect_zh(key: str) -> str:
    return ASPECT_TYPES_ZH.get(key, key)


def _natal_sections(chart: dict, title: str) -> list[dict]:
    """本命盘分节（星盘/行运/推运/合盘共用）。"""
    secs: list[dict] = [{"type": "h1", "text": title}]
    secs.append({"type": "para", "text": _meta_line(chart)})

    secs.append({"type": "h2", "text": "四轴"})
    rows = [["轴点", "星座", "度数"]]
    for key, zh in ANGLE_ZH.items():
        a = chart.get(key)
        if a:
            rows.append([zh, a["sign"], f"{a['degree']:.1f}°"])
    secs.append({"type": "table", "rows": rows})

    secs.append({"type": "h2", "text": "行星位置"})
    rows = [["行星", "星座", "度数", "宫位", "逆行"]]
    for name in PLANET_IDS:
        p = chart["planets"][name]
        rows.append([
            PLANET_ZH[name], p["sign"], f"{p['degree']:.1f}°",
            str(p.get("house", "—")), "℞" if p.get("retrograde") else "—",
        ])
    secs.append({"type": "table", "rows": rows})

    points = chart.get("points")
    if points:
        secs.append({"type": "h2", "text": "虚点 / 小行星"})
        rows = [["虚点", "星座", "度数", "宫位"]]
        for key, p in points.items():
            rows.append([
                POINT_ZH.get(key, key), p["sign"], f"{p['degree']:.1f}°",
                f"第{p.get('house', '?')}宫",
            ])
        secs.append({"type": "table", "rows": rows})

    if chart.get("aspects"):
        secs.append({"type": "h2", "text": "相位"})
        secs.append({
            "type": "list",
            "items": [
                f"{PLANET_ZH[a['p1']]} {_aspect_zh(a['typeEn'])} {PLANET_ZH[a['p2']]}（{a['orb']}°）"
                for a in chart["aspects"]
            ],
        })

    if chart.get("patterns"):
        secs.append({"type": "h2", "text": "格局"})
        secs.append({
            "type": "list",
            "items": [p["type"] + "：" + "、".join(PLANET_ZH[x] for x in p["planets"]) for p in chart["patterns"]],
        })

    secs.append({"type": "h2", "text": "宫位"})
    rows = [["宫位", "星座", "宫内行星"]]
    for i in range(1, 13):
        h = chart["houses"][str(i)]
        planets = "、".join(PLANET_ZH[x] for x in h["planets"]) or "—"
        rows.append([str(i), h["sign"], planets])
    secs.append({"type": "table", "rows": rows})
    return secs


def _natal_sections_chart_or_block(data: dict) -> list[dict]:
    """提取"本命盘"数据：顶层（star_chart/transit/progression）或 personA/personB（synastry）。"""
    if "planets" in data and "houses" in data:
        return _natal_sections(data, "本命盘分析报告")
    return []


def _transit_sections(data: dict) -> list[dict]:
    secs = _natal_sections(data, "行运分析报告")
    t = data.get("transit", {})
    if not t:
        return secs
    meta = data.get("meta", {})
    secs.append({"type": "h2", "text": "行运"})
    secs.append({
        "type": "para",
        "text": f"行运时刻 {meta.get('transitDateTime', '')}（{meta.get('transitTimezone', '')}）",
    })
    rows = [["行运行星", "星座", "度数", "落本命宫"]]
    for name in PLANET_IDS:
        p = t["planets"].get(name)
        if p:
            retro = " ℞" if p.get("retrograde") else ""
            rows.append([PLANET_ZH[name], p["sign"], f"{p['degree']:.1f}°",
                         f"第{p.get('natalHouse', '?')}宫{retro}"])
    secs.append({"type": "table", "rows": rows})
    if t.get("aspects"):
        secs.append({"type": "h2", "text": "行运对本命相位"})
        secs.append({
            "type": "list",
            "items": [
                f"行运{PLANET_ZH[a['transit']]} {_aspect_zh(a['type'])} 本命{PLANET_ZH[a['natal']]}（{a['orb']}°）"
                for a in t["aspects"]
            ],
        })
    if t.get("angleAspects"):
        secs.append({"type": "h2", "text": "行运对四轴相位"})
        secs.append({
            "type": "list",
            "items": [
                f"行运{PLANET_ZH[a['transit']]} {_aspect_zh(a['type'])} {ANGLE_ZH[a['angle']]}（{a['orb']}°）"
                for a in t["angleAspects"]
            ],
        })
    return secs


def _progression_sections(data: dict) -> list[dict]:
    secs = _natal_sections(data, "推运分析报告")
    p = data.get("progressed", {})
    if not p:
        return secs
    meta = data.get("meta", {})
    ptype = meta.get("progressionType", "secondary")
    type_zh = {
        "secondary": "次限（一天=一年）",
        "tertiary": "三限（一天=一月）",
        "solar_arc": "太阳弧",
        "solar_return": "日返",
        "lunar_return": "月返",
    }
    secs.append({"type": "h2", "text": f"推运（{type_zh.get(ptype, ptype)}）"})
    secs.append({
        "type": "para",
        "text": f"年龄 {meta.get('age', '')} 岁 · 推运日期 {meta.get('progressedDate', '')} · "
                f"推运天数 {meta.get('ageDays', '')} 天",
    })
    rows = [["推运行星", "星座", "度数", "落本命宫"]]
    for name in PLANET_IDS:
        pp = p["planets"].get(name)
        if pp:
            retro = " ℞" if pp.get("retrograde") else ""
            rows.append([PLANET_ZH[name], pp["sign"], f"{pp['degree']:.1f}°",
                         f"第{pp.get('natalHouse', '?')}宫{retro}"])
    secs.append({"type": "table", "rows": rows})
    if p.get("aspects"):
        secs.append({"type": "h2", "text": "推运内部相位"})
        secs.append({
            "type": "list",
            "items": [
                f"{PLANET_ZH[a['p1']]} {_aspect_zh(a['typeEn'])} {PLANET_ZH[a['p2']]}（{a['orb']}°）"
                for a in p["aspects"]
            ],
        })
    if p.get("natalAspects"):
        secs.append({"type": "h2", "text": "推运对本命相位"})
        secs.append({
            "type": "list",
            "items": [
                f"推运{PLANET_ZH[a['progressed']]} {_aspect_zh(a['type'])} 本命{PLANET_ZH[a['natal']]}（{a['orb']}°）"
                for a in p["natalAspects"]
            ],
        })
    return secs


def _synastry_sections(data: dict) -> list[dict]:
    secs: list[dict] = [{"type": "h1", "text": "合盘分析报告"}]
    meta = data.get("meta", {})
    pa, pb = meta.get("personA", {}), meta.get("personB", {})
    secs.append({
        "type": "para",
        "text": f"A 方出生 {pa.get('birthDateTime', '')}（{pa.get('timezone', '')}） · "
                f"B 方出生 {pb.get('birthDateTime', '')}（{pb.get('timezone', '')}）",
    })

    chart_a = data.get("personA", {})
    chart_b = data.get("personB", {})
    secs += _natal_sections(chart_a, "A 方本命盘")
    secs += _natal_sections(chart_b, "B 方本命盘")

    syn = data.get("synastry", {})
    if not syn:
        return secs
    secs.append({"type": "h2", "text": "合盘相位（A × B）"})
    syn_items = [
            f"A {PLANET_ZH[a['a']]} {_aspect_zh(a['type'])} B {PLANET_ZH[a['b']]}（{a['orb']}°）"
            for a in syn.get("aspects", [])
        ]
    if syn_items:
        secs.append({"type": "list", "items": syn_items})
    else:
        secs.append({"type": "para", "text": "无主相位"})

    def _overlay_table(owner: str, overlay: dict) -> None:
        rows = [["宫位", "星座", f"{owner} 方行星"]]
        for i in range(1, 13):
            h = overlay[str(i)]
            planets = "、".join(PLANET_ZH[x] for x in h["planets"]) or "—"
            rows.append([str(i), h["sign"], planets])
        secs.append({"type": "table", "rows": rows})

    secs.append({"type": "h2", "text": "A 方行星落 B 方宫位"})
    _overlay_table("A", syn.get("aInBHouses", {}))
    secs.append({"type": "h2", "text": "B 方行星落 A 方宫位"})
    _overlay_table("B", syn.get("bInAHouses", {}))

    if syn.get("angleAspects"):
        secs.append({"type": "h2", "text": "行星对对方四轴相位"})
        secs.append({
            "type": "list",
            "items": [
                f"{a['owner']}方 {PLANET_ZH[a['planet']]} {_aspect_zh(a['type'])} "
                f"{a['chart']}方 {ANGLE_ZH[a['angle']]}（{a['orb']}°）"
                for a in syn["angleAspects"]
            ],
        })
    return secs


def _electional_sections(data: dict) -> list[dict]:
    secs: list[dict] = [{"type": "h1", "text": "择时报告"}]
    meta = data.get("meta", {})
    secs.append({
        "type": "para",
        "text": f"起始日期 {meta.get('startDate', '')} · 天数 {meta.get('days', '')} · "
                f"时区 {meta.get('timezone', '')} · 采样小时 {meta.get('sampleHour', '')}"
                + (f" · 用途：{meta['purpose']}" if meta.get("purpose") else "")
                + (" · 含本命盘（个人择时）" if meta.get("hasNatal") else " · 未含本命盘"),
    })
    if data.get("heuristics"):
        secs.append({"type": "para", "text": data["heuristics"]})
    secs.append({"type": "h2", "text": "候选日期（按评分降序）"})
    rows = [["日期", "评分", "摘要"]]
    for c in data.get("candidates", []):
        rows.append([c["date"], f"{c['score']:.1f}", c.get("summary", "")])
    secs.append({"type": "table", "rows": rows})
    if data.get("bestDate"):
        secs.append({"type": "para", "text": f"综合最佳日期：{data['bestDate']}"})
    return secs


def _sections(data: dict) -> list[dict]:
    """按数据结构自动识别报告类型并生成分节。"""
    if "transit" in data:
        secs = _transit_sections(data)
    elif "progressed" in data:
        secs = _progression_sections(data)
    elif "personA" in data and "synastry" in data:
        secs = _synastry_sections(data)
    elif "candidates" in data:
        secs = _electional_sections(data)
    else:
        secs = _natal_sections(data, "星盘分析报告")
    secs.append({"type": "h2", "text": "免责声明"})
    secs.append({"type": "para", "text": DISCLAIMER})
    secs.append({
        "type": "para",
        "text": f"报告生成时间：{datetime.now().astimezone().strftime('%Y-%m-%d %H:%M:%S')}",
    })
    return secs


def render_markdown(data: dict) -> str:
    """星盘结果 → Markdown 文本。"""
    lines: list[str] = []
    for sec in _sections(data):
        if sec["type"] == "h1":
            lines.append(f"# {sec['text']}")
        elif sec["type"] == "h2":
            lines.append(f"## {sec['text']}")
        elif sec["type"] == "para":
            lines.append(sec["text"])
        elif sec["type"] == "list":
            for item in sec["items"]:
                lines.append(f"- {item}")
        elif sec["type"] == "table":
            rows = sec["rows"]
            if not rows:
                continue
            lines.append("| " + " | ".join(rows[0]) + " |")
            lines.append("| " + " | ".join("---" for _ in rows[0]) + " |")
            for row in rows[1:]:
                lines.append("| " + " | ".join(row) + " |")
        lines.append("")
    return "\n".join(lines).strip() + "\n"


def render_pdf(data: dict) -> bytes:
    """星盘结果 → PDF 字节流（reportlab，CJK 内嵌字体 STSong-Light）。"""
    from io import BytesIO

    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
    from reportlab.lib.units import mm
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.cidfonts import UnicodeCIDFont
    from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

    pdfmetrics.registerFont(UnicodeCIDFont("STSong-Light"))
    styles = getSampleStyleSheet()
    h1 = ParagraphStyle("zh-h1", parent=styles["Title"], fontName="STSong-Light", fontSize=20, leading=26)
    h2 = ParagraphStyle("zh-h2", parent=styles["Heading2"], fontName="STSong-Light", fontSize=15, leading=20)
    body = ParagraphStyle("zh-body", parent=styles["BodyText"], fontName="STSong-Light", fontSize=11, leading=16)
    cell = ParagraphStyle("zh-cell", parent=body, fontSize=9.5, leading=13)

    buf = BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4, topMargin=18 * mm, bottomMargin=18 * mm)
    story: list = []
    for sec in _sections(data):
        if sec["type"] == "h1":
            story.append(Paragraph(sec["text"], h1))
        elif sec["type"] == "h2":
            story.append(Spacer(1, 4 * mm))
            story.append(Paragraph(sec["text"], h2))
        elif sec["type"] == "para":
            story.append(Paragraph(sec["text"], body))
        elif sec["type"] == "list":
            for item in sec["items"]:
                story.append(Paragraph(f"• {item}", body))
        elif sec["type"] == "table":
            rows = [
                [Paragraph(str(c) or "—", cell) for c in row]
                for row in sec["rows"]
            ]
            table = Table(rows, repeatRows=1)
            table.setStyle(TableStyle([
                ("FONTNAME", (0, 0), (-1, -1), "STSong-Light"),
                ("BACKGROUND", (0, 0), (-1, 0), colors.Color(0.92, 0.92, 0.94)),
                ("GRID", (0, 0), (-1, -1), 0.4, colors.Color(0.75, 0.75, 0.75)),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LEFTPADDING", (0, 0), (-1, -1), 4),
                ("RIGHTPADDING", (0, 0), (-1, -1), 4),
                ("TOPPADDING", (0, 0), (-1, -1), 2),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
            ]))
            story.append(table)
        story.append(Spacer(1, 2 * mm))
    doc.build(story)
    return buf.getvalue()
