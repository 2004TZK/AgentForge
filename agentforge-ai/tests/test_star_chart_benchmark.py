"""M1 验收基准测试：star_chart 计算结果 vs pyswisseph 期望值。

依赖：
  - pyswisseph（需在 Docker 容器或安装了编译依赖的环境中运行）
  - tests/fixtures/benchmark_cases.json（由 scripts/generate_benchmark.py 生成）

运行方式：
  cd agentforge-ai && pytest tests/test_star_chart_benchmark.py -v

验收标准：关键点位（行星黄经、四轴、宫位头）误差 < 0.5°
"""
import json
import math
from pathlib import Path

import pytest

FIXTURES_DIR = Path(__file__).parent / "fixtures"
FIXTURE_FILE = FIXTURES_DIR / "benchmark_cases.json"

# 验收阈值（度）
TOLERANCE = 0.5


def _load_benchmark():
    """加载基准用例 JSON。"""
    if not FIXTURE_FILE.exists():
        pytest.skip(f"基准用例文件不存在: {FIXTURE_FILE}。"
                    f"请先运行: python scripts/generate_benchmark.py")
    data = json.loads(FIXTURE_FILE.read_text(encoding="utf-8"))
    return data


def _angular_diff(a: float, b: float) -> float:
    """计算两个黄经值之间的最小角度差（0-180°）。"""
    diff = abs(a - b) % 360
    return min(diff, 360 - diff)


@pytest.fixture(scope="module")
def benchmark_data():
    return _load_benchmark()


@pytest.fixture(scope="module")
def star_chart_calculate():
    """导入 star_chart.calculate_chart 函数。"""
    from app.tools.star_chart import calculate_chart
    return calculate_chart


# ─────────────────── 参数化测试 ───────────────────

def _planet_test_ids():
    """生成参数化测试 ID。"""
    data = _load_benchmark()
    ids = []
    params = []
    for case in data["cases"]:
        for planet_name in case["expected"]["planets"]:
            ids.append(f"{case['label']}__{planet_name}")
            params.append((case, planet_name))
    return params, ids


class TestBenchmarkPlanets:
    """测试行星黄经精度。"""

    @pytest.mark.parametrize("case,planet_name", [
        *[(c, p) for c in _load_benchmark()["cases"] for p in c["expected"]["planets"]]
    ] if FIXTURE_FILE.exists() else [],
        ids=[
        *[
            f"{c['label']}__{p}"
            for c in _load_benchmark()["cases"]
            for p in c["expected"]["planets"]
        ]
    ] if FIXTURE_FILE.exists() else ["skip"])
    def test_planet_longitude(self, star_chart_calculate, case, planet_name):
        """行星黄经误差 < 0.5°。"""
        result = star_chart_calculate(
            birth_date=case["birthDate"],
            birth_time=case["birthTime"],
            latitude=case["latitude"],
            longitude=case["longitude"],
            timezone=case["timezone"],
        )
        result_json = json.loads(result) if isinstance(result, str) else result
        actual = result_json["planets"][planet_name]["longitude"]
        expected = case["expected"]["planets"][planet_name]["longitude"]
        diff = _angular_diff(actual, expected)
        assert diff < TOLERANCE, (
            f"{case['label']} / {planet_name}: "
            f"黄经 actual={actual:.4f}° expected={expected:.4f}° diff={diff:.4f}° "
            f"(阈值={TOLERANCE}°)"
        )


class TestBenchmarkAngles:
    """测试四轴精度。"""

    @pytest.mark.parametrize("case", _load_benchmark()["cases"] if FIXTURE_FILE.exists() else [],
        ids=[c["label"] for c in _load_benchmark()["cases"]] if FIXTURE_FILE.exists() else ["skip"])
    def test_ascendant(self, star_chart_calculate, case):
        """上升点(ASC)黄经误差 < 0.5°。"""
        result = star_chart_calculate(
            birth_date=case["birthDate"],
            birth_time=case["birthTime"],
            latitude=case["latitude"],
            longitude=case["longitude"],
            timezone=case["timezone"],
        )
        result_json = json.loads(result) if isinstance(result, str) else result
        actual = result_json["ascendant"]["longitude"]
        expected = case["expected"]["ascendant"]["longitude"]
        diff = _angular_diff(actual, expected)
        assert diff < TOLERANCE, (
            f"{case['label']} ASC: "
            f"actual={actual:.4f}° expected={expected:.4f}° diff={diff:.4f}°"
        )

    @pytest.mark.parametrize("case", _load_benchmark()["cases"] if FIXTURE_FILE.exists() else [],
        ids=[c["label"] for c in _load_benchmark()["cases"]] if FIXTURE_FILE.exists() else ["skip"])
    def test_midheaven(self, star_chart_calculate, case):
        """天顶(MC)黄经误差 < 0.5°。"""
        result = star_chart_calculate(
            birth_date=case["birthDate"],
            birth_time=case["birthTime"],
            latitude=case["latitude"],
            longitude=case["longitude"],
            timezone=case["timezone"],
        )
        result_json = json.loads(result) if isinstance(result, str) else result
        actual = result_json["midheaven"]["longitude"]
        expected = case["expected"]["midheaven"]["longitude"]
        diff = _angular_diff(actual, expected)
        assert diff < TOLERANCE, (
            f"{case['label']} MC: "
            f"actual={actual:.4f}° expected={expected:.4f}° diff={diff:.4f}°"
        )


class TestBenchmarkHouses:
    """测试宫位头精度。"""

    @pytest.mark.parametrize("case", _load_benchmark()["cases"] if FIXTURE_FILE.exists() else [],
        ids=[c["label"] for c in _load_benchmark()["cases"]] if FIXTURE_FILE.exists() else ["skip"])
    def test_house_cusps(self, star_chart_calculate, case):
        """12宫头黄经误差 < 0.5°。"""
        result = star_chart_calculate(
            birth_date=case["birthDate"],
            birth_time=case["birthTime"],
            latitude=case["latitude"],
            longitude=case["longitude"],
            timezone=case["timezone"],
        )
        result_json = json.loads(result) if isinstance(result, str) else result
        for house_num in range(1, 13):
            actual = result_json["houses"][str(house_num)]["cusp"]
            expected = case["expected"]["houses"][str(house_num)]["cusp"]
            diff = _angular_diff(actual, expected)
            assert diff < TOLERANCE, (
                f"{case['label']} House {house_num}: "
                f"actual={actual:.4f}° expected={expected:.4f}° diff={diff:.4f}°"
            )


class TestBenchmarkDST:
    """专项验证：历史夏令时/跨日/时区案例。"""

    def test_china_dst_1988(self, star_chart_calculate, benchmark_data):
        """中国 1988 夏令时案例：验证 UTC 换算正确。"""
        case = next(c for c in benchmark_data["cases"] if "china_dst_1988" in c["label"])
        result = star_chart_calculate(
            birth_date=case["birthDate"],
            birth_time=case["birthTime"],
            latitude=case["latitude"],
            longitude=case["longitude"],
            timezone=case["timezone"],
        )
        result_json = json.loads(result) if isinstance(result, str) else result
        # 验证 UTC 时间正确（夏令时 UTC+9，10:00 CST → 01:00 UTC）
        assert "01:00" in result_json["meta"]["utDateTime"], (
            f"夏令时换算错误: 期望 UTC 01:00，实际 {result_json['meta']['utDateTime']}"
        )

    def test_china_dst_1991_last_year(self, star_chart_calculate, benchmark_data):
        """中国 1991 夏令时末年：验证最后一年 DST 仍生效。"""
        case = next(c for c in benchmark_data["cases"] if "1991" in c["label"])
        result = star_chart_calculate(
            birth_date=case["birthDate"],
            birth_time=case["birthTime"],
            latitude=case["latitude"],
            longitude=case["longitude"],
            timezone=case["timezone"],
        )
        result_json = json.loads(result) if isinstance(result, str) else result
        # 1991年7月15日 10:00 DST(UTC+9) → 01:00 UTC
        assert "01:00" in result_json["meta"]["utDateTime"], (
            f"1991夏令时换算错误: 期望 UTC 01:00，实际 {result_json['meta']['utDateTime']}"
        )

    def test_post_dst_no_summer_offset(self, star_chart_calculate, benchmark_data):
        """1995年夏季无DST：验证 1992 后不再有夏令时偏移。"""
        case = next(c for c in benchmark_data["cases"] if "post_dst" in c["label"])
        result = star_chart_calculate(
            birth_date=case["birthDate"],
            birth_time=case["birthTime"],
            latitude=case["latitude"],
            longitude=case["longitude"],
            timezone=case["timezone"],
        )
        result_json = json.loads(result) if isinstance(result, str) else result
        # 1995年7月20日 14:00 CST(UTC+8) → 06:00 UTC（非DST）
        assert "06:00" in result_json["meta"]["utDateTime"], (
            f"非夏令时换算错误: 期望 UTC 06:00，实际 {result_json['meta']['utDateTime']}"
        )

    def test_xinjiang_urumqi_timezone(self, star_chart_calculate, benchmark_data):
        """新疆时区：Asia/Urumqi UTC+6，验证与北京时区差异。"""
        case = next(c for c in benchmark_data["cases"] if "xinjiang" in c["label"])
        result = star_chart_calculate(
            birth_date=case["birthDate"],
            birth_time=case["birthTime"],
            latitude=case["latitude"],
            longitude=case["longitude"],
            timezone=case["timezone"],
        )
        result_json = json.loads(result) if isinstance(result, str) else result
        # 1990-06-15 12:00 Urumqi(UTC+6) → 06:00 UTC
        assert "06:00" in result_json["meta"]["utDateTime"], (
            f"新疆时区换算错误: 期望 UTC 06:00，实际 {result_json['meta']['utDateTime']}"
        )

    def test_cross_day_midnight(self, star_chart_calculate, benchmark_data):
        """跨日案例：北京 2000-01-01 02:00 → UTC 1999-12-31 18:00。"""
        case = next(c for c in benchmark_data["cases"] if "cross_day" in c["label"])
        result = star_chart_calculate(
            birth_date=case["birthDate"],
            birth_time=case["birthTime"],
            latitude=case["latitude"],
            longitude=case["longitude"],
            timezone=case["timezone"],
        )
        result_json = json.loads(result) if isinstance(result, str) else result
        assert "1999-12-31" in result_json["meta"]["utDateTime"], (
            f"跨日换算错误: 期望 UTC 1999-12-31，实际 {result_json['meta']['utDateTime']}"
        )
