"""star_chart 工具单元测试：城市库 / 输入解析 / 错误处理 / 高纬度降级 / Schema 注册。"""
import json

import pytest

from app.tools import registry
from app.tools import star_chart


def _calc(**kwargs) -> dict:
    defaults = {"birth_date": "", "birth_time": ""}
    defaults.update(kwargs)
    return star_chart.calculate_chart(**defaults)


class TestCityLookup:
    def test_beijing_city(self):
        result = _calc(birth_date="1994-05-20", birth_time="14:30", city="北京")
        assert result["meta"]["timezone"] == "Asia/Shanghai"
        assert result["meta"]["houseSystem"] == "placidus"
        # 与基准用例（同日期同时间）太阳黄经误差 < 0.5°
        assert abs(result["planets"]["sun"]["longitude"] - 59.0256) < 0.5

    def test_city_priority_over_coords(self):
        """city 与经纬度同时提供时以 city 为准（忽略经纬度）。"""
        result = _calc(
            birth_date="1994-05-20", birth_time="14:30",
            city="北京", latitude=0.0, longitude=0.0, timezone="UTC",
        )
        assert result["meta"]["timezone"] == "Asia/Shanghai"

    def test_english_name_lookup(self):
        result = _calc(birth_date="1994-05-20", birth_time="14:30", city="beijing")
        assert result["meta"]["timezone"] == "Asia/Shanghai"

    def test_unknown_city_raises(self):
        with pytest.raises(ValueError, match="不在内置城市库"):
            _calc(birth_date="1994-05-20", birth_time="14:30", city="亚特兰蒂斯")


class TestBirthText:
    def test_birth_text_chinese(self):
        result = _calc(birth_text="1994-05-20 14:30 北京")
        assert result["meta"]["timezone"] == "Asia/Shanghai"
        assert result["meta"]["birthDateTime"] == "1994-05-20T14:30:00+08:00"
        assert result["birthText"] == "1994-05-20 14:30 北京"

    def test_birth_text_zh_format(self):
        result = _calc(birth_text="1994年5月20日 14点30分 上海")
        assert result["meta"]["timezone"] == "Asia/Shanghai"

    def test_birth_text_missing_time(self):
        with pytest.raises(ValueError, match="缺少出生时间"):
            _calc(birth_text="1994-05-20 北京")


class TestErrors:
    def test_missing_birth_time(self):
        with pytest.raises(ValueError, match="缺少出生日期或时间"):
            _calc(birth_date="1994-05-20", birth_time="",
                  latitude=39.9, longitude=116.4, timezone="Asia/Shanghai")

    def test_manual_coords_missing_timezone(self):
        with pytest.raises(ValueError, match="必须提供 timezone"):
            _calc(birth_date="1994-05-20", birth_time="14:30",
                  latitude=39.9, longitude=116.4)

    def test_missing_location(self):
        with pytest.raises(ValueError, match="缺少出生地点"):
            _calc(birth_date="1994-05-20", birth_time="14:30")

    def test_year_out_of_range(self):
        with pytest.raises(ValueError, match="1800-2399"):
            _calc(birth_date="1799-01-01", birth_time="12:00",
                  latitude=39.9, longitude=116.4, timezone="Asia/Shanghai")

    def test_invalid_timezone(self):
        with pytest.raises(ValueError, match="无效的 IANA 时区"):
            _calc(birth_date="1994-05-20", birth_time="14:30",
                  latitude=39.9, longitude=116.4, timezone="Mars/Olympus")

    def test_invalid_house_system(self):
        with pytest.raises(ValueError, match="宫位制"):
            _calc(birth_date="1994-05-20", birth_time="14:30",
                  latitude=39.9, longitude=116.4, timezone="Asia/Shanghai",
                  house_system="not_a_system")


class TestHighLatitudeFallback:
    def test_arctic_fallback_whole_sign(self):
        """70°N Placidus 失败 → 自动降级整宫制并标注。"""
        result = _calc(birth_date="2000-01-01", birth_time="12:00",
                       latitude=70.0, longitude=0.0, timezone="UTC")
        assert result["meta"]["houseSystemFallback"] is True
        assert result["meta"]["houseSystem"] == "whole_sign"
        assert len(result["houses"]) == 12

    def test_mohe_placidus_ok(self):
        """中国最北城市漠河（53.5°N）Placidus 正常，无需降级。"""
        result = _calc(birth_date="1995-06-15", birth_time="12:00",
                       latitude=53.4712, longitude=122.5349, timezone="Asia/Shanghai")
        assert result["meta"]["houseSystemFallback"] is False
        assert result["meta"]["houseSystem"] == "placidus"


class TestOutputStructure:
    def test_demo_case_structure(self):
        result = _calc(birth_date="1994-05-20", birth_time="14:30", city="北京")
        assert set(result["planets"]) == {
            "sun", "moon", "mercury", "venus", "mars",
            "jupiter", "saturn", "uranus", "neptune", "pluto",
        }
        for p in result["planets"].values():
            assert 1 <= p["house"] <= 12
            assert "longitude" in p and "sign" in p and "retrograde" in p
        assert len(result["houses"]) == 12
        for h in result["houses"].values():
            assert "cusp" in h and "planets" in h
        for a in result["aspects"]:
            assert {"p1", "p2", "type", "typeEn", "orb"} <= set(a)
        for pat in result["patterns"]:
            assert pat["type"] in (
                "大三角", "T三角", "大十字", "星群", "风筝", "神秘长方形",
                "上帝之指", "摇篮", "大六分相", "双Yod",
                "束型", "碗型", "桶型", "火车头型", "跷跷板型", "撒型", "扇型",
            )

    def test_whole_sign_requested(self):
        result = _calc(birth_date="1994-05-20", birth_time="14:30",
                       city="北京", house_system="whole_sign")
        assert result["meta"]["houseSystem"] == "whole_sign"
        assert result["meta"]["houseSystemFallback"] is False

    def test_sidereal(self):
        result = _calc(birth_date="1994-05-20", birth_time="14:30",
                       city="北京", zodiac="sidereal")
        assert result["meta"]["zodiac"] == "sidereal"
        assert result["meta"]["ayanamsa"] == "Lahiri"
        trop = _calc(birth_date="1994-05-20", birth_time="14:30", city="北京")
        diff = (trop["planets"]["sun"]["longitude"]
                - result["planets"]["sun"]["longitude"]) % 360
        assert 20 < diff < 28  # Ayanamsa ≈ 23.8°


class TestRegistry:
    def test_registered(self):
        assert registry.is_registered("star_chart")
        assert "star_chart" in registry.list_tools()

    def test_openai_tool_schema(self):
        tool = registry.to_openai_tool("star_chart")
        assert tool["function"]["name"] == "star_chart"
        props = tool["function"]["parameters"]["properties"]
        for key in ("birthDate", "birthTime", "city", "latitude", "longitude",
                    "timezone", "houseSystem", "zodiac", "birthText"):
            assert key in props

    def test_call_tool_not_truncated(self):
        text = registry.call_tool(
            "star_chart", {"birthDate": "1994-05-20", "birthTime": "14:30", "city": "北京"}
        )
        assert len(text) > 500  # 完整排盘 JSON 不被截断
        data = json.loads(text)
        assert data["meta"]["timezone"] == "Asia/Shanghai"

    def test_call_tool_error_text(self):
        text = registry.call_tool(
            "star_chart", {"birthDate": "1994-05-20", "birthTime": "14:30", "city": "亚特兰蒂斯"}
        )
        assert text.startswith("[star_chart] 错误：")
