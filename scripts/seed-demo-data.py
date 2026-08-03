"""AgentForge 演示数据种子脚本（M4 收尾版）。

用途：在清空业务数据后重建一套"完整、可操作"的演示数据：
  1. demo 用户（注册 + 登录）
  2. Agent A「Java 专家」（对话模式 + calculator/github 工具）
  3. Agent B「知识库助手」（对话模式 + Spring 知识库文档，走真实 RAG 入库）
  4. 工作流「GitHub 项目分析」（llm 提取 → tool 查询 → llm 报告）
  5. Agent C「GitHub 分析官」（工作流模式，绑定上述工作流）
  6. 为三个 Agent 各创建一个会话并做一次真实对话验证

前置：docker compose 服务已启动（http://localhost）。
运行：python scripts/seed-demo-data.py（依赖 httpx，可用 agentforge-ai/.venv）
重复执行：用户已存在时直接登录，其余按名称幂等创建。
"""
import sys
import time

import httpx

# Windows 控制台默认 GBK，回答可能含 emoji，统一用 UTF-8 输出
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

BASE_URL = "http://localhost/api"
DEMO_USER = "demo"
DEMO_PASSWORD = "demo123"
DEMO_EMAIL = "demo@agentforge.local"

# 知识库演示文档（真实内容，供 RAG 检索验证）
SPRING_KNOWLEDGE = """# Spring 核心知识速查

## Spring Bean 生命周期
Spring 容器中的 Bean 生命周期大致分为以下阶段：
1. 实例化：容器根据配置创建 Bean 实例（构造方法）。
2. 属性填充：通过 Setter 或字段注入依赖（@Autowired、构造注入）。
3. Aware 回调：Bean 若实现 BeanNameAware、ApplicationContextAware 等接口，会收到容器回调。
4. BeanPostProcessor 前置处理：postProcessBeforeInitialization 在初始化前执行。
5. 初始化：执行 @PostConstruct、InitializingBean.afterPropertiesSet 或自定义 init-method。
6. BeanPostProcessor 后置处理：postProcessAfterInitialization（AOP 代理通常在此阶段生成）。
7. 使用：Bean 被容器持有，供其他组件调用。
8. 销毁：容器关闭时执行 @PreDestroy、DisposableBean.destroy 或自定义 destroy-method。

## Spring Boot 自动配置
@SpringBootApplication 包含 @EnableAutoConfiguration，它根据 classpath 中的依赖
自动装配常用组件（如 DataSource、Jackson、WebMvc），并允许通过属性文件覆盖。
条件注解（@ConditionalOnClass、@ConditionalOnMissingBean）控制自动配置是否生效。

## 依赖注入的三种方式
- 构造器注入：推荐用于必选依赖，保证不可变性与可测试性。
- Setter 注入：用于可选依赖，可后续替换实现。
- 字段注入（@Autowired 直接标注字段）：简洁但不易测试，官方不推荐。
"""


def new_client(timeout: float = 300.0) -> httpx.Client:
    return httpx.Client(base_url=BASE_URL, timeout=timeout)


def register_or_login(client: httpx.Client) -> str:
    """注册 demo 用户；已存在则直接登录。返回 JWT。"""
    resp = client.post("/auth/register", json={
        "username": DEMO_USER, "password": DEMO_PASSWORD, "email": DEMO_EMAIL,
    })
    data = resp.json()
    if data.get("code") == 0:
        print(f"[用户] 注册成功: {DEMO_USER}")
    else:
        print(f"[用户] 用户已存在或注册跳过（{data.get('message')}），尝试登录")
    resp = client.post("/auth/login", json={
        "username": DEMO_USER, "password": DEMO_PASSWORD,
    })
    data = resp.json()
    if data.get("code") != 0:
        raise RuntimeError(f"登录失败: {data}")
    token = data["data"]["token"]
    client.headers["Authorization"] = f"Bearer {token}"
    print(f"[用户] 登录成功: {DEMO_USER}")
    return token


def create_agent(client: httpx.Client, payload: dict) -> dict:
    """按名称幂等创建：同名 Agent 已存在时直接复用。"""
    page = client.get("/agent/page", params={"page": 1, "size": 100}).json()
    for item in page.get("data", {}).get("list", []):
        if item["name"] == payload["name"]:
            print(f"[Agent] 复用已存在: {payload['name']} (id={item['id']})")
            return item
    resp = client.post("/agent", json=payload)
    data = resp.json()
    if data.get("code") != 0:
        raise RuntimeError(f"创建 Agent 失败: {data}")
    return data["data"]


def upload_doc_and_wait(client: httpx.Client, agent_id: int, filename: str,
                        content: str, timeout: float = 240.0) -> str:
    """上传知识库文档并轮询至 READY / FAILED。"""
    existed = client.get("/file/list", params={"agentId": agent_id, "page": 1, "size": 100}).json()
    for doc in existed.get("data", {}).get("list", []):
        if doc["fileName"] == filename and doc["status"] == "READY":
            print(f"[知识库] 复用已入库文档: {filename} (docId={doc['id']})")
            return doc["status"]
    with open(filename, "w", encoding="utf-8") as f:
        f.write(content)
    with open(filename, "rb") as f:
        resp = client.post("/file/upload", params={"agentId": agent_id},
                           files={"file": (filename, f, "text/markdown")})
    data = resp.json()
    if data.get("code") != 0:
        raise RuntimeError(f"上传文档失败: {data}")
    doc_id = data["data"]["id"]
    print(f"[知识库] 已上传 {filename} (docId={doc_id})，等待入库…")
    deadline = time.time() + timeout
    while time.time() < deadline:
        lst = client.get("/file/list", params={"agentId": agent_id, "page": 1, "size": 10}).json()
        for doc in lst.get("data", {}).get("list", []):
            if doc["id"] == doc_id:
                status = doc["status"]
                if status == "READY":
                    print(f"[知识库] 入库完成: {filename} → {status}")
                    return status
                if status == "FAILED":
                    raise RuntimeError(f"文档入库失败: {doc}")
        time.sleep(3)
    raise RuntimeError("等待文档入库超时")


def create_workflow(client: httpx.Client, name: str, description: str) -> dict:
    """创建工作流「GitHub 项目分析」：llm 提取 → tool 查询 → llm 报告。"""
    existed = client.get("/workflows", params={"page": 1, "size": 100}).json()
    for item in existed.get("data", {}).get("list", []):
        if item["name"] == name:
            print(f"[工作流] 复用已存在: {name} (id={item['id']})")
            return item
    nodes = [
        {
            "nodeKey": "extract_repo",
            "nodeType": "llm",
            "params": {
                "prompt": "你是 GitHub 项目分析师。用户需求：{message}\n"
                          "请从消息中提取要分析的 GitHub 仓库路径（owner/repo 格式），"
                          "只输出仓库路径本身，不要任何其他内容。",
                "temperature": 0.2,
            },
            "nextNode": "fetch_github",
        },
        {
            "nodeKey": "fetch_github",
            "nodeType": "tool",
            "params": {"tool": "github", "payload": {"repo": "{extract_repo}"}},
            "nextNode": "gen_report",
        },
        {
            "nodeKey": "gen_report",
            "nodeType": "llm",
            "params": {
                "prompt": "你是 GitHub 项目分析专家。以下是查询到的项目信息：\n{fetch_github}\n"
                          "请输出一份简洁的中文分析报告：项目名称、Star 数、主要语言、"
                          "项目简介，以及 2-3 句你的点评。",
                "temperature": 0.5,
            },
            "nextNode": None,
        },
    ]
    resp = client.post("/workflows", json={"name": name, "description": description, "nodes": nodes})
    data = resp.json()
    if data.get("code") != 0:
        raise RuntimeError(f"创建工作流失败: {data}")
    workflow = data["data"]
    print(f"[工作流] 已创建: {name} (id={workflow['id']}, {len(workflow['nodes'])} 节点)")
    return workflow


def create_session(client: httpx.Client, agent_id: int, name: str) -> int:
    resp = client.post("/chat/session", json={"agentId": agent_id, "name": name})
    data = resp.json()
    if data.get("code") != 0:
        raise RuntimeError(f"创建会话失败: {data}")
    session_id = data["data"]["id"]
    print(f"[会话] 已创建: {name} (sessionId={session_id})")
    return session_id


def chat(client: httpx.Client, agent_id: int, session_id: int, message: str) -> dict:
    print(f"[聊天] {message}")
    resp = client.post("/chat", json={"agentId": agent_id, "sessionId": session_id, "message": message})
    data = resp.json()
    if data.get("code") != 0:
        raise RuntimeError(f"聊天失败: {data}")
    result = data["data"]
    print(f"  → 回答: {(result.get('answer') or '')[:120].replace(chr(10), ' ')}")
    if result.get("toolCalls"):
        print(f"  → 工具调用: {result['toolCalls']}")
    if result.get("sources"):
        print(f"  → 来源引用: {[s.get('file') for s in result['sources']]}")
    return result


def main() -> None:
    client = new_client()
    register_or_login(client)

    # 1) Agent A：Java 专家（对话模式 + 工具）
    java_agent = create_agent(client, {
        "name": "Java 专家",
        "description": "资深 Java 工程师，擅长 Spring Boot 与工具调用",
        "systemPrompt": "你是一名资深 Java 工程师，帮助用户解决 Java 与 Spring Boot 问题。"
                        "回答简洁、附代码示例；需要计算时调用计算器工具。",
        "modelName": "qwen3.7-plus",
        "temperature": 0.7,
        "tools": [
            {"toolName": "calculator", "toolConfig": {}, "enabled": True},
            {"toolName": "github", "toolConfig": {}, "enabled": True},
        ],
        "mode": "chat",
        "visibility": "PUBLIC",
    })
    print(f"[Agent] 已创建: {java_agent['name']} (id={java_agent['id']})")

    # 2) Agent B：知识库助手（对话模式 + RAG 文档）
    kb_agent = create_agent(client, {
        "name": "知识库助手",
        "description": "基于 Spring 知识库回答问题的助手",
        "systemPrompt": "你是知识库问答助手。只依据提供的资料回答；资料不足时如实说明，不要编造。",
        "modelName": "qwen3.7-plus",
        "temperature": 0.3,
        "tools": [],
        "mode": "chat",
        "visibility": "PUBLIC",
    })
    print(f"[Agent] 已创建: {kb_agent['name']} (id={kb_agent['id']})")
    upload_doc_and_wait(client, kb_agent["id"], "spring-notes.md", SPRING_KNOWLEDGE)

    # 3) 工作流 + Agent C：GitHub 分析官（工作流模式）
    workflow = create_workflow(client, "GitHub 项目分析", "提取仓库 → 查询项目信息 → 生成分析报告")
    analyst_agent = create_agent(client, {
        "name": "GitHub 分析官",
        "description": "绑定工作流的分析助手：自动完成查仓库→算指标→出报告",
        "systemPrompt": "你是 GitHub 项目分析官。收到需求后运行绑定的工作流完成项目分析。",
        "modelName": "qwen3.7-plus",
        "temperature": 0.5,
        "tools": [],
        "mode": "workflow",
        "workflowId": workflow["id"],
        "visibility": "PUBLIC",
    })
    print(f"[Agent] 已创建: {analyst_agent['name']} (id={analyst_agent['id']}, workflowId={workflow['id']})")

    # 4) 为三个 Agent 创建会话并做真实对话验证
    s1 = create_session(client, java_agent["id"], "工具演示")
    s2 = create_session(client, kb_agent["id"], "知识库问答")
    s3 = create_session(client, analyst_agent["id"], "工作流演示")

    print("\n===== 对话验证 =====")
    # 纯算式消息：LLM 决策或规则兜底均能稳定触发 calculator
    chat(client, java_agent["id"], s1, "(128+64)/8")
    chat(client, kb_agent["id"], s2, "Spring Bean 的生命周期是怎样的？")
    chat(client, analyst_agent["id"], s3, "分析一下 github.com/spring-projects/spring-boot")

    print("\n===== 演示数据就绪 =====")
    print(f"登录账号: {DEMO_USER} / {DEMO_PASSWORD}")
    print(f"Agent A Java 专家 (id={java_agent['id']})：工具演示")
    print(f"Agent B 知识库助手 (id={kb_agent['id']})：知识库问答")
    print(f"Agent C GitHub 分析官 (id={analyst_agent['id']})：工作流演示")
    print(f"工作流 (id={workflow['id']})：GitHub 项目分析")


if __name__ == "__main__":
    try:
        main()
    except (httpx.HTTPError, RuntimeError, KeyError) as exc:
        print(f"\n种子脚本执行失败: {exc}", file=sys.stderr)
        sys.exit(1)
