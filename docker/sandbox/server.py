"""AgentForge sandbox 沙箱执行服务（工具定义开发文档 v3.0 §6/§7 阶段三）。

受限执行用户自定义代码工具：
- 仅 AI 服务可经内部网络访问（compose network_mode: none，无外网）
- 子进程降权为 nobody（非 root）、RLIMIT 内存/CPU 限制、超时强杀
- 输出/返回值截断；错误分类（Timeout / Memory / Syntax / Runtime）
- 内部 Token 鉴权 + 固定窗口限流 + 并发上限
"""
import json
import logging
import os
import resource
import subprocess
import sys
import threading
import time
from typing import Any

from fastapi import Depends, FastAPI, Header, HTTPException, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
logger = logging.getLogger("sandbox")

# ---------------- 常量 ----------------
INTERNAL_TOKEN = os.environ.get("SANDBOX_INTERNAL_TOKEN", "dev-sandbox-token")
MAX_SOURCE_CHARS = 50 * 1024          # 代码大小上限（50KB）
MAX_OUTPUT_CHARS = 1_000_000          # stdout/结果截断上限（1MB 字符）
MAX_CONCURRENCY = 4                   # 服务级最大并发执行数
RATE_LIMIT_PER_MINUTE = 120           # 固定窗口限流（QPS ~2/s）
NOBODY_UID = 65534
NOBODY_GID = 65534
DEFAULT_TIMEOUT = 10
DEFAULT_MEMORY_MB = 256

app = FastAPI(title="AgentForge Sandbox", version="1.0.0")


# ---------------- 限流 / 并发 ----------------

class _RateLimiter:
    """固定窗口限流：60s 窗口内最多 N 次请求。"""

    def __init__(self, max_per_minute: int):
        self.max_per_minute = max_per_minute
        self.lock = threading.Lock()
        self.window_start = time.time()
        self.count = 0

    def allow(self) -> bool:
        with self.lock:
            now = time.time()
            if now - self.window_start >= 60:
                self.window_start = now
                self.count = 0
            self.count += 1
            return self.count <= self.max_per_minute


rate_limiter = _RateLimiter(RATE_LIMIT_PER_MINUTE)
concurrency_semaphore = threading.Semaphore(MAX_CONCURRENCY)


def require_token(x_internal_token: str = Header(default="")) -> None:
    if x_internal_token != INTERNAL_TOKEN:
        raise HTTPException(status_code=401, detail="unauthorized")


# ---------------- 请求/响应模型 ----------------

class RunRequest(BaseModel):
    language: str = Field(description="python / javascript")
    source: str = Field(description="用户代码（定义 run(args)）")
    args: dict = Field(default_factory=dict, description="LLM 依据 Schema 填充的入参")
    limits: dict = Field(default_factory=dict, description="{timeoutSeconds, memoryMb}")


# ---------------- 执行原语 ----------------

def _apply_limits(memory_mb: int, cpu_seconds: int) -> None:
    """preexec 回调：子进程内存/CPU 限制 + 降权 nobody（非 root）。"""
    try:
        resource.setrlimit(resource.RLIMIT_AS,
                           (memory_mb * 1024 * 1024, memory_mb * 1024 * 1024))
        resource.setrlimit(resource.RLIMIT_CPU, (cpu_seconds, cpu_seconds))
        os.setgid(NOBODY_GID)
        os.setuid(NOBODY_UID)
    except Exception as exc:  # noqa: BLE001 - 子进程启动阶段失败由 Popen 异常捕获
        sys.stderr.write(f"limits setup failed: {exc}\n")
        os._exit(125)


def _run_subprocess(command: list[str], source_file: str, args_json: str,
                    timeout: int, memory_mb: int) -> dict:
    """受限子进程执行：stdin 传入参数 JSON，捕获 stdout/stderr，超时强杀。"""
    stdout_limit = MAX_OUTPUT_CHARS
    try:
        proc = subprocess.Popen(
            command,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            preexec_fn=lambda: _apply_limits(memory_mb, timeout + 5),
        )
    except Exception as exc:  # noqa: BLE001
        return {"ok": False, "error": f"子进程启动失败: {exc}", "durationMs": 0}

    start = time.monotonic()
    try:
        out, err = proc.communicate(input=args_json.encode("utf-8"), timeout=timeout)
    except subprocess.TimeoutExpired:
        proc.kill()
        proc.communicate()
        return {"ok": False, "error": "TimeoutError", "durationMs": int((time.monotonic() - start) * 1000)}
    duration_ms = int((time.monotonic() - start) * 1000)
    del source_file  # 代码文件由调用方管理生命周期

    stdout = out.decode("utf-8", errors="replace")[:stdout_limit]
    stderr = err.decode("utf-8", errors="replace")[:2000]

    if proc.returncode != 0:
        if "MemoryError" in stderr or "Killed" in stderr:
            return {"ok": False, "error": "MemoryLimitError", "stdout": stdout,
                    "durationMs": duration_ms}
        return {"ok": False, "error": _classify_error(stderr, stdout),
                "stdout": stdout, "durationMs": duration_ms}

    # 成功：取 stdout 最后一行（JSON 结果），其余视为日志输出
    lines = [ln for ln in stdout.splitlines() if ln.strip()]
    result_text = lines[-1] if lines else ""
    logs = "\n".join(lines[:-1])
    try:
        result = json.loads(result_text)
    except (json.JSONDecodeError, IndexError):
        result = stdout
    return {"ok": True, "result": result, "stdout": logs[:MAX_OUTPUT_CHARS],
            "durationMs": duration_ms}


def _classify_error(stderr: str, stdout: str) -> str:
    """错误分类：SyntaxError / NameError / TypeError / Runtime…（取最后一条异常摘要）。"""
    text = (stderr or stdout).strip()
    if not text:
        return "RuntimeError"
    lines = text.splitlines()
    for line in reversed(lines):
        lowered = line.lower()
        for marker in ("syntaxerror", "modulenotfounderror", "nameerror", "typeerror",
                       "valueerror", "keyerror", "indexerror", "zerodivisionerror",
                       "referenceerror", "runtimeerror", "uncaught", "timeouterror"):
            if marker in lowered:
                return line.strip()[:300]
    return lines[-1].strip()[:300] if lines else "RuntimeError"


def _run_python(source: str, args: dict, limits: dict) -> dict:
    code = f"{source}\n\n" + (
        "import json\n"
        "_ARGS = json.loads('''{args}''')\n"
        "_result = run(_ARGS)\n"
        "print(json.dumps(_result, ensure_ascii=False))\n"
    ).format(args=json.dumps(args, ensure_ascii=False).replace("'", "\\'"))
    source_file = f"/tmp/run_{os.getpid()}_{threading.get_ident()}.py"
    with open(source_file, "w", encoding="utf-8") as f:
        f.write(code)
    try:
        return _run_subprocess([sys.executable, "-I", "-E", source_file], source_file,
                               json.dumps(args, ensure_ascii=False),
                               limits.get("timeoutSeconds", DEFAULT_TIMEOUT),
                               limits.get("memoryMb", DEFAULT_MEMORY_MB))
    finally:
        try:
            os.remove(source_file)
        except OSError:
            pass


def _run_javascript(source: str, args: dict, limits: dict) -> dict:
    code = f"{source}\n\n" + (
        "const __args = JSON.parse(await new Promise((res) => {\n"
        "  let d = '';\n"
        "  process.stdin.on('data', (c) => { d += c; });\n"
        "  process.stdin.on('end', () => res(d));\n"
        "}));\n"
        "const __result = run(__args);\n"
        "console.log(JSON.stringify(__result));\n"
    )
    source_file = f"/tmp/run_{os.getpid()}_{threading.get_ident()}.mjs"
    with open(source_file, "w", encoding="utf-8") as f:
        f.write(code)
    try:
        return _run_subprocess(["node", source_file], source_file,
                               json.dumps(args, ensure_ascii=False),
                               limits.get("timeoutSeconds", DEFAULT_TIMEOUT),
                               limits.get("memoryMb", DEFAULT_MEMORY_MB))
    finally:
        try:
            os.remove(source_file)
        except OSError:
            pass


# ---------------- 接口 ----------------

@app.exception_handler(Exception)
async def _unhandled(_request: Request, exc: Exception) -> JSONResponse:
    """兜底：任何未捕获异常转为 200 {ok:false}，保证主链路可读。"""
    logger.exception("sandbox 未捕获异常")
    return JSONResponse(status_code=200, content={"ok": False, "error": f"SandboxError: {exc}"})


@app.post("/run")
def run(request: RunRequest, _auth: None = Depends(require_token)) -> dict:
    """受限执行用户代码：{language, source, args, limits} → {ok, result|error, stdout, durationMs}。"""
    if not rate_limiter.allow():
        return {"ok": False, "error": "RateLimitError: 请求过于频繁，请稍后重试", "durationMs": 0}
    if not concurrency_semaphore.acquire(blocking=False):
        return {"ok": False, "error": "ConcurrencyLimitError: 沙箱并发已满，请稍后重试", "durationMs": 0}
    try:
        language = request.language
        if language not in ("python", "javascript"):
            return {"ok": False, "error": f"不支持的执行语言: {language}", "durationMs": 0}
        source = request.source or ""
        if len(source) > MAX_SOURCE_CHARS:
            return {"ok": False, "error": "SourceTooLargeError: 代码大小超过 50KB 上限", "durationMs": 0}

        start = time.monotonic()
        if language == "python":
            result = _run_python(source, request.args, request.limits)
        else:
            result = _run_javascript(source, request.args, request.limits)
        result["durationMs"] = int((time.monotonic() - start) * 1000)
        return result
    finally:
        concurrency_semaphore.release()
