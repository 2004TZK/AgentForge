"""星盘报告导出接口：POST /star-chart/report（Markdown / PDF）。

V2「报告导出」：接收星盘工具结果 JSON，返回 Markdown 文本或 PDF 字节流。
仅限内部调用（X-Internal-Token），前端经后端代理或直接以 markdown 客户端生成。
"""
from fastapi import APIRouter, Depends
from fastapi.responses import PlainTextResponse, Response
from pydantic import BaseModel

from app.api.deps import require_internal_token
from app.services import star_report

router = APIRouter(
    prefix="/star-chart",
    tags=["star-chart"],
    dependencies=[Depends(require_internal_token)],
)


class ReportRequest(BaseModel):
    """报告导出请求：chart 为任一星盘工具结果 JSON，kind 为 markdown 或 pdf。"""

    chart: dict
    kind: str = "markdown"


@router.post("/report")
def generate_report(req: ReportRequest) -> Response:
    """生成星盘报告（Markdown / PDF）。"""
    kind = (req.kind or "markdown").lower()
    if kind == "pdf":
        pdf = star_report.render_pdf(req.chart)
        return Response(
            content=pdf,
            media_type="application/pdf",
            headers={
                "Content-Disposition": 'attachment; filename="star-chart-report.pdf"',
            },
        )
    md = star_report.render_markdown(req.chart)
    return PlainTextResponse(md, media_type="text/markdown; charset=utf-8")
