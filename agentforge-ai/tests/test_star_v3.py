"""V3 增强单元测试：多宫位制 / 多 Ayanamsa / 虚点小行星 / 次要相位 /
容许度流派 / 入出相位 / 17 种格局 / 推运扩展（三限·太阳弧·日返·月返）。"""
import json

import pytest

from app.tools import registry, star_base, star_chart, star_progression

BIRTH = {"birth_date": "1994-05-20", "birth_time": "14:30", "city": "北京"}

HOUSE_SYSTEMS = [
    "whole_sign", "equal", "koch", "regiomontanus", "campanus",
    "porphyry", "topocentric", "alcabitius", "morinus",
]


class TestHouseSystems:
    @pytest.mark.parametrize("hs", HOUSE_SYSTEMS)
    def test_house_system_works(self, hs):
        r = star_chart.calculate_chart(**BIRTH, house_system=hs)
        assert r["meta"]["houseSystem"] == hs
        assert r["meta"]["houseSystemFallback"] is False
        assert len(r["houses"]) == 12

    def test_placidus_default(self):
        r = star_chart.calculate_chart(**BIRTH)
        assert r["meta"]["houseSystem"] == "placidus"

    def test_invalid_house_system_raises(self):
        with pytest.raises(ValueError, match="宫位制"):
            star_chart.calculate_chart(**BIRTH, house_system="not_a_system")

    def test_arctic_fallback_still_works(self):
        r = star_chart.calculate_chart(
            birth_date="2000-01-01", birth_time="12:00",
            latitude=70.0, longitude=0.0, timezone="UTC",
        )
        assert r["meta"]["houseSystemFallback"] is True
        assert r["meta"]["houseSystem"] == "whole_sign"


class TestAyanamsa:
    @pytest.mark.parametrize("key, zh", [
        ("raman", "Raman"),
        ("krishnamurti", "Krishnamurti"),
        ("fagan_bradley", "Fagan/Bradley"),
        ("deluce", "DeLuce"),
        ("j2000", "J2000"),
        ("suryasiddhanta", "SuryaSiddhanta"),
        ("true_citra", "True Citra"),
        ("ss_revati", "SS Revati"),
    ])
    def test_ayanamsa_systems(self, key, zh):
        r = star_chart.calculate_chart(**BIRTH, zodiac="sidereal", ayanamsa=key)
        assert r["meta"]["ayanamsa"] == zh
        assert r["meta"]["zodiac"] == "sidereal"

    def test_ayanamsa_differs_from_lahiri(self):
        base = star_chart.calculate_chart(**BIRTH, zodiac="sidereal")
        other = star_chart.calculate_chart(**BIRTH, zodiac="sidereal", ayanamsa="fagan_bradley")
        diff = abs(base["planets"]["sun"]["longitude"] - other["planets"]["sun"]["longitude"]) % 360
        assert min(diff, 360 - diff) > 0.1

    def test_invalid_ayanamsa(self):
        with pytest.raises(ValueError, match="Ayanamsa"):
            star_chart.calculate_chart(**BIRTH, zodiac="sidereal", ayanamsa="foo")


class TestPoints:
    def test_default_nodes(self):
        r = star_chart.calculate_chart(**BIRTH)
        assert set(r["points"]) == {"north_node", "south_node"}
        assert 1 <= r["points"]["north_node"]["house"] <= 12
        assert r["points"]["north_node"]["retrograde"] is True
        diff = abs(
            r["points"]["north_node"]["longitude"]
            - r["points"]["south_node"]["longitude"]
        ) % 360
        assert abs(min(diff, 360 - diff) - 180) < 1e-6

    def test_extended_points(self):
        r = star_chart.calculate_chart(
            **BIRTH,
            points=[
                "chiron", "ceres", "pallas", "juno", "vesta",
                "lilith", "true_node", "true_south_node", "part_of_fortune", "vertex",
            ],
        )
        for k in (
            "chiron", "ceres", "pallas", "juno", "vesta",
            "lilith", "true_node", "true_south_node", "part_of_fortune", "vertex",
        ):
            assert k in r["points"]
            assert "longitude" in r["points"][k]

    def test_points_via_registry(self):
        data = json.loads(registry.call_tool(
            "star_chart", {
                "birthDate": "1994-05-20",
                "birthTime": "14:30",
                "city": "北京",
                "points": ["chiron", "north_node"],
            }
        ))
        assert set(data["points"]) == {"chiron", "north_node"}


class TestAspects:
    def test_minor_aspects_enabled(self):
        r = star_chart.calculate_chart(
            **BIRTH,
            aspects=[
                "conjunction", "sextile", "square", "trine", "opposition",
                "semi_sextile", "semi_square", "quintile",
                "sesquiquadrate", "biquintile", "quincunx",
            ],
        )
        types = {a["typeEn"] for a in r["aspects"]}
        assert types & {
            "semi_sextile", "semi_square", "quintile",
            "sesquiquadrate", "biquintile", "quincunx",
        }

    def test_aspect_has_direction(self):
        r = star_chart.calculate_chart(**BIRTH)
        assert r["aspects"]
        for a in r["aspects"]:
            assert a["direction"] in ("applying", "separating", "exact")
            assert "angle" in a

    def test_angle_aspects_via_targets(self):
        r = star_chart.calculate_chart(
            **BIRTH,
            aspect_targets=["sun", "moon", "ascendant", "midheaven"],
        )
        involved = {a["p1"] for a in r["aspects"]} | {a["p2"] for a in r["aspects"]}
        assert involved & {"ascendant", "midheaven"}

    def test_classical_orb_differs(self):
        r1 = star_chart.calculate_chart(**BIRTH)
        r2 = star_chart.calculate_chart(**BIRTH, orb_mode="classical")
        assert r2["meta"]["orbMode"] == "classical"
        # 同一对行星/相位的容许度在两种流派下应存在差异
        modern = {(a["p1"], a["p2"], a["typeEn"]): a["orb"] for a in r1["aspects"]}
        classical = {(a["p1"], a["p2"], a["typeEn"]): a["orb"] for a in r2["aspects"]}
        # 容许度流派不同 → 判出的相位集合应不同
        assert set(modern) != set(classical)

    def test_custom_orbs(self):
        r = star_chart.calculate_chart(**BIRTH, custom_orbs={"conjunction": 12})
        for a in r["aspects"]:
            if a["typeEn"] == "conjunction":
                assert a["orb"] <= 12


class TestPatternsSynthetic:
    """用合成黄经直接测 find_patterns 的格局判定（不依赖真实星历）。"""

    def _planets(self, lons):
        names = list(star_base.PLANET_IDS)
        assert len(lons) == len(names)
        return {
            name: {
                "longitude": lon,
                "house": (i % 12) + 1,
                "signIndex": int(lon // 30) % 12,
            }
            for i, (name, lon) in enumerate(zip(names, lons))
        }

    def _types(self, p, **kw):
        return {x["type"] for x in star_base.find_patterns(p, **kw)}

    def test_kite(self):
        assert "风筝" in self._types(self._planets([0, 120, 240, 180, 300, 310, 320, 330, 340, 350]))

    def test_yod_needs_quincunx(self):
        p = self._planets([0, 150, 210, 300, 310, 320, 330, 340, 350, 355])
        assert "上帝之指" not in self._types(p)
        assert "上帝之指" in self._types(
            p,
            aspect_keys=[
                "conjunction", "sextile", "square", "trine",
                "opposition", "quincunx",
            ],
        )

    def test_double_yod(self):
        p = self._planets([0, 150, 210, 60, 270, 300, 310, 320, 330, 340])
        assert "双Yod" in self._types(
            p,
            aspect_keys=[
                "conjunction", "sextile", "square", "trine",
                "opposition", "quincunx",
            ],
        )

    def test_mystic_rectangle(self):
        assert "神秘长方形" in self._types(self._planets([0, 60, 180, 240, 300, 310, 320, 330, 340, 350]))

    def test_cradle(self):
        assert "摇篮" in self._types(self._planets([0, 10, 65, 245, 300, 310, 320, 330, 340, 350]))

    def test_grand_cross(self):
        assert "大十字" in self._types(self._planets([0, 90, 180, 270, 300, 310, 320, 330, 340, 350]))

    def test_grand_sextile(self):
        assert "大六分相" in self._types(self._planets([0, 60, 120, 180, 240, 300, 310, 320, 330, 340]))

    def test_bundle(self):
        assert "束型" in self._types(self._planets([0, 15, 30, 45, 60, 75, 90, 105, 118, 119]))

    def test_bowl(self):
        assert "碗型" in self._types(self._planets([0, 20, 40, 60, 80, 100, 120, 140, 160, 179.9]))

    def test_bucket(self):
        p = self._planets([0, 20, 40, 60, 80, 100, 120, 140, 170, 250])
        types = self._types(p)
        assert "桶型" in types
        pat = next(x for x in star_base.find_patterns(p) if x["type"] == "桶型")
        assert pat["handle"]

    def test_locomotive(self):
        assert "火车头型" in self._types(self._planets([0, 25, 50, 75, 100, 125, 150, 175, 200, 230]))

    def test_seesaw(self):
        assert "跷跷板型" in self._types(self._planets([0, 10, 20, 30, 40, 200, 210, 220, 300, 310]))

    def test_splash(self):
        assert "撒型" in self._types(self._planets([0, 32, 64, 96, 128, 160, 192, 224, 256, 288]))

    def test_splay(self):
        assert "扇型" in self._types(self._planets([0, 5, 10, 100, 105, 200, 205, 305, 310, 315]))


class TestProgressionV3:
    def test_tertiary_offset(self):
        r = star_progression.calculate_progression(**BIRTH, age=30, progression_type="tertiary")
        assert r["meta"]["progressionType"] == "tertiary"
        assert r["meta"]["progressedDate"] == "1995-05-15"  # 30 年 × 12 天 = 360 天

    def test_secondary_offset_fixed(self):
        """次限偏移 = 年龄年数（天）：30 岁 → 推运历书日期 = 出生 + 30 天。"""
        r = star_progression.calculate_progression(**BIRTH, age=30, progression_type="secondary")
        assert r["meta"]["ageDays"] == round(30 * 365.2425)
        assert r["meta"]["progressedDate"] == "1994-06-19"
        assert r["progressed"]["planets"]["sun"]["signIndex"] == 2  # 双子座

    def test_solar_arc(self):
        r = star_progression.calculate_progression(**BIRTH, age=30, progression_type="solar_arc")
        arc = r["progressed"]["arcDegrees"]
        assert 20 < arc < 35  # 30 年太阳弧 ≈ 29-30°
        for a, b in (("sun", "moon"), ("venus", "mars")):
            d1 = (r["planets"][a]["longitude"] - r["planets"][b]["longitude"]) % 360
            d2 = (
                r["progressed"]["planets"][a]["longitude"]
                - r["progressed"]["planets"][b]["longitude"]
            ) % 360
            assert abs(d1 - d2) < 1e-6

    def test_solar_return(self):
        r = star_progression.calculate_progression(**BIRTH, age=30, progression_type="solar_return")
        assert r["meta"]["returnDate"]
        diff = abs(
            r["progressed"]["planets"]["sun"]["longitude"]
            - r["planets"]["sun"]["longitude"]
        ) % 360
        assert min(diff, 360 - diff) < 1.0

    def test_lunar_return(self):
        r = star_progression.calculate_progression(**BIRTH, age=30, progression_type="lunar_return")
        assert r["meta"]["returnDate"]
        diff = abs(
            r["progressed"]["planets"]["moon"]["longitude"]
            - r["planets"]["moon"]["longitude"]
        ) % 360
        assert min(diff, 360 - diff) < 1.0

    def test_invalid_progression_type(self):
        with pytest.raises(ValueError, match="推运类型"):
            star_progression.calculate_progression(**BIRTH, age=30, progression_type="foo")


class TestTransitV3:
    def test_transit_points_and_direction(self):
        data = json.loads(registry.call_tool("transit_chart", {
            "birthText": "1994-05-20 14:30 北京",
            "transitDate": "2026-08-06",
            "transitTime": "12:00",
        }))
        assert "points" in data["transit"]
        assert 1 <= data["transit"]["points"]["north_node"]["natalHouse"] <= 12
        for asp in data["transit"]["aspects"]:
            assert asp["direction"] in ("applying", "separating", "exact")


class TestSchemaV3:
    def test_star_chart_schema_new_params(self):
        tool = registry.to_openai_tool("star_chart")
        props = tool["function"]["parameters"]["properties"]
        for key in ("ayanamsa", "orbMode", "aspects", "customOrbs", "aspectTargets", "points"):
            assert key in props

    def test_progression_schema_type(self):
        tool = registry.to_openai_tool("progression_chart")
        props = tool["function"]["parameters"]["properties"]
        assert "progressionType" in props
