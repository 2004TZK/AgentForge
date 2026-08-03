"""Github Tool：通过 GitHub 公开 API 查询仓库信息（名称/Star/语言/简介）。"""
import logging

import httpx

logger = logging.getLogger(__name__)

API_TIMEOUT = 10


def query_repo(repo_path: str) -> dict:
    """查询仓库，repo_path 形如 'owner/repo'，如 'spring-projects/spring-boot'。"""
    repo_path = repo_path.strip().strip("/")
    if "/" not in repo_path:
        raise ValueError("仓库格式应为 owner/repo，如 spring-projects/spring-boot")
    url = f"https://api.github.com/repos/{repo_path}"
    try:
        resp = httpx.get(url, timeout=API_TIMEOUT, headers={"Accept": "application/vnd.github+json"})
        if resp.status_code == 404:
            raise ValueError(f"仓库不存在: {repo_path}")
        resp.raise_for_status()
        data = resp.json()
        return {
            "fullName": data.get("full_name", repo_path),
            "description": data.get("description"),
            "stars": data.get("stargazers_count", 0),
            "language": data.get("language"),
            "htmlUrl": data.get("html_url"),
        }
    except httpx.HTTPError as exc:
        logger.warning("GitHub API 调用失败: %s", exc)
        raise RuntimeError("GitHub API 不可用") from exc


SCHEMA = {
    "name": "github",
    "description": "查询 GitHub 仓库的名称、Star 数、语言与简介。",
    "parameters": {"repo": {"type": "string", "description": "仓库路径 owner/repo"}},
}
