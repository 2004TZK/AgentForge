"""V2 报告导出测试：Markdown / PDF 渲染 + API 端点。"""
from fastapi.testclient import TestClient

from app.core.config import settings
from app.main import app
from app.services import star_report
from app.tools import star_electional, star_progression, star_synastry, star_transit
from app.tools.star_chart import calculate_chart

client = TestClient(app)


def _natal() -> dict:
    return calculate_chart(
        birth_date="1994-05-20",
        birth_time="14:30",
        city="北京",
    )


def _transit() -> dict:
    return star_transit.calculate_transit(
        birth_date="1994-05-20",
        birth_time="14:30",
        city="北京",
        transit_date="2026-08-06",
        transit_time="12:00",
    )


def _progression() -> dict:
    return star_progression.calculate_progression(
        birth_date="1994-05-20",
        birth_time="14:30",
        city="北京",
        age=30,
    )


def _synastry() -> dict:
    return star_synastry.calculate_synastry(
        a_birth_date="1994-05-20",
        a_birth_time="14:30",
        a_city="北京",
        b_birth_date="1995-08-08",
        b_birth_time="08:00",
        b_city="上海",
    )


def _electional() -> dict:
    return star_electional.calculate_electional(
        start_date="2026-08-06",
        days=7,
        birth_date="1994-05-20",
        birth_time="14:30",
        city="北京",
    )


class TestMarkdown:
    def test_natal_markdown_sections(self):
        md = star_report.render_markdown(_natal())
        assert md.startswith("#")
        for keyword in ("四轴", "行星位置", "宫位", "相位", "免责声明"):
            assert keyword in md

    def test_transit_markdown(self):
        md = star_report.render_markdown(_transit())
        assert "行运" in md
        assert "行运对本命相位" in md or "行运" in md

    def test_progression_markdown(self):
        md = star_report.render_markdown(_progression())
        assert "推运" in md

    def test_synastry_markdown(self):
        md = star_report.render_markdown(_synastry())
        assert "A 方本命盘" in md
        assert "B 方本命盘" in md
        assert "合盘相位" in md

    def test_electional_markdown(self):
        md = star_report.render_markdown(_electional())
        assert "择时" in md
        assert "最佳日期" in md

    def test_disclaimer_present(self):
        for data in (_natal(), _transit(), _progression(), _synastry(), _electional()):
            assert "仅供娱乐与自我探索参考" in star_report.render_markdown(data)


class TestPdf:
    def test_natal_pdf(self):
        pdf = star_report.render_pdf(_natal())
        assert pdf.startswith(b"%PDF")
        assert len(pdf) > 2000

    def test_all_kinds_pdf(self):
        for data in (_transit(), _progression(), _synastry(), _electional()):
            pdf = star_report.render_pdf(data)
            assert pdf.startswith(b"%PDF")
            assert len(pdf) > 1500


class TestReportApi:
    def test_markdown_endpoint(self):
        resp = client.post(
            "/star-chart/report",
            json={"chart": _natal(), "kind": "markdown"},
            headers={"X-Internal-Token": settings.internal_token},
        )
        assert resp.status_code == 200
        assert "text/markdown" in resp.headers["content-type"]
        assert "星盘" in resp.text

    def test_pdf_endpoint(self):
        resp = client.post(
            "/star-chart/report",
            json={"chart": _natal(), "kind": "pdf"},
            headers={"X-Internal-Token": settings.internal_token},
        )
        assert resp.status_code == 200
        assert resp.headers["content-type"] == "application/pdf"
        assert resp.content.startswith(b"%PDF")

    def test_endpoint_requires_token(self):
        resp = client.post("/star-chart/report", json={"chart": _natal()})
        assert resp.status_code == 401
