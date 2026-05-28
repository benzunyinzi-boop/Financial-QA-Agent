# AGENTS.md

## 项目概述

- 项目名称：LangChain ReAct Agent 智能客服
- 业务描述：扫地机器人垂直领域的 AI 智能客服系统
- 服务类型：AI Agent + RAG 应用
- 主要协议：HTTP (FastAPI) / WebSocket

## 技术栈

- 语言：Python 3.10+
- Web 框架：FastAPI（计划）/ Streamlit（当前）
- AI 框架：LangChain 0.3.x + LangGraph 0.2.x
- LLM：阿里通义千问 qwen3-max (DashScope SDK)
- Embedding：text-embedding-v4 (DashScope)
- 向量库：Chroma 0.5.x（开发/测试）/ Milvus（生产待迁移）
- 前端：React 18 + TypeScript + TailwindCSS v4 + shadcn/ui
- 状态管理：Zustand
- 部署：Docker + docker-compose
- 日志：Python logging（多级日志 + 文件输出）
- 配置：YAML + python-dotenv

## 项目结构

```
.
├── api/                    # FastAPI 路由层（计划）
│   ├── routers/
│   ├── middleware/
│   └── schemas/
├── agent/                  # ReAct Agent 核心逻辑
│   ├── react_agent.py      # Agent 主类
│   └── tools/              # 工具函数集合
│       ├── agent_tools.py  # 工具定义
│       └── middleware.py   # 中间件（动态提示词切换）
├── rag/                    # RAG 检索增强模块
│   ├── rag_service.py      # RAG 总结服务
│   └── vector_store.py     # 向量存储服务
├── model/                  # 模型工厂层
│   └── factory.py          # LLM/Embedding 工厂
├── prompts/                # 提示词模板
│   ├── main_prompt.txt
│   ├── rag_summarize.txt
│   └── report_prompt.txt
├── config/                 # YAML 配置文件
│   ├── agent.yml
│   ├── chroma.yml
│   ├── prompts.yml
│   └── rag.yml
├── utils/                  # 通用工具函数
│   ├── config_handler.py
│   ├── file_handler.py
│   ├── logger_handler.py
│   ├── path_tool.py
│   └── prompt_loader.py
├── data/                   # 知识库数据
│   ├── *.txt / *.pdf       # 知识库文档
│   └── external/           # 外部数据（用户记录等）
├── frontend/               # React 前端（独立项目）
│   ├── src/
│   ├── package.json
│   └── vite.config.ts
├── tests/                  # 测试代码（计划）
├── chroma_db/              # Chroma 向量库持久化目录
├── logs/                   # 日志输出目录
├── app.py                  # Streamlit 应用入口（当前）
├── requirements.txt
├── Dockerfile
├── docker-compose.yml
└── README.md
```

## 分层架构规范

遵循 api → agent → rag → model 四层架构：

- **api 层**（计划）：FastAPI 路由，参数校验（Pydantic），请求/响应转换，不含业务逻辑
- **agent 层**：ReAct Agent 核心逻辑，工具调用编排，对话状态管理
- **rag 层**：向量检索、文档加载、RAG 总结，调用 model 层
- **model 层**：LLM/Embedding 模型的统一工厂接口，封装 DashScope 调用
- **禁止跨层调用**：api 不能直接调 rag 或 model
- **禁止循环依赖**：依赖方向只能向下（api → agent → rag → model）

## 编码规范

### 命名（遵循 PEP 8）

- 文件名：snake_case（`user_service.py`）
- 模块名：小写单词，不用下划线（`userservice` 或 `user_service` 均可）
- 类名：PascalCase（`ReactAgent`, `VectorStoreService`）
- 函数/方法：snake_case（`load_document`, `rag_summarize`）
- 常量：全大写下划线分隔（`MAX_CHUNK_SIZE`, `DEFAULT_MODEL`）
- 私有属性/方法：单下划线前缀（`_internal_method`）

### 异常处理

- 始终捕获具体异常类型，避免裸 `except:`
- 使用 `try/except/finally` 结构，确保资源释放
- 异常信息通过 logger 记录，包含堆栈跟踪（`exc_info=True`）
- 业务异常自定义异常类（继承 `Exception`），放在 `utils/exceptions.py`
- API 响应统一格式：`{"code": 0, "message": "ok", "data": {}}`
- 不要用 `raise Exception("xxx")`，使用具体异常类型

### 异步编程

- I/O 密集型操作（LLM 调用、向量检索、文件读写）优先使用 `async/await`
- 使用 `asyncio.gather()` 并发执行独立任务
- 长时间运行的任务使用 `asyncio.create_task()` 或 `BackgroundTasks`（FastAPI）
- 避免在 async 函数中调用阻塞的同步代码，使用 `run_in_executor` 包装

### 日志

- 使用 `utils/logger_handler.py` 提供的 logger，不用 `print()`
- 日志必须携带 `trace_id`（通过 context 传递），便于链路追踪
- 级别使用规范：
  - `DEBUG`：调试信息（变量值、中间状态）
  - `INFO`：关键流程节点（用户请求、工具调用、模型响应）
  - `WARNING`：可恢复的异常（重试成功、降级处理）
  - `ERROR`：需关注的错误（模型调用失败、向量库异常）
- 不要在循环中打日志，避免日志风暴
- 敏感信息（API Key、用户输入的隐私数据）需脱敏

## AI 开发规范

### Prompt 管理

- 所有提示词模板放在 `prompts/` 目录，使用 `.txt` 文件
- 通过 `utils/prompt_loader.py` 统一加载，不要硬编码在代码中
- 提示词文件命名清晰：`main_prompt.txt`, `rag_summarize.txt`, `report_prompt.txt`
- 提示词变更需记录版本和原因（Git commit message）

### 模型调用

- 统一通过 `model/factory.py` 的工厂类获取模型实例
- 不要在业务代码中直接 `import ChatTongyi` 或 `DashScopeEmbeddings`
- 模型配置（model_name）通过 `config/rag.yml` 管理，便于切换
- LLM 调用必须设置 timeout（建议 30s）
- 捕获模型调用异常，实现 fallback 降级（主模型失败 → 备用模型 → 模板回复）

### Token 成本控制

- 简单问答优先使用小模型（qwen-turbo / qwen-plus）
- 复杂推理、报告生成才用 qwen3-max
- RAG 检索后的上下文控制在合理长度（避免超长 context）
- 记录每次调用的 Token 消耗，定期分析优化

### RAG 检索

- 检索策略：Top-K 召回（当前 k=3）→ Reranker 精排（计划）
- 文档分块：chunk_size=500-800, chunk_overlap=50-100（当前 200 太小）
- 向量化时在 metadata 中记录 `document_id`、`source_file`、`chunk_index`
- 检索失败时有降级策略（返回空上下文，LLM 基于自身知识回答）

### 工具定义

- 使用 `@tool` 装饰器定义工具函数
- docstring 必须清晰描述工具用途、入参格式、返回值
- 工具函数内部捕获异常，返回友好错误信息（不要让 Agent 看到堆栈）
- 工具调用通过中间件监控（`agent/tools/middleware.py`）

## API 设计规范（FastAPI）

### HTTP (RESTful)

- URL 使用 kebab-case：`/api/v1/chat-stream`, `/api/v1/knowledge-base`
- 资源命名用复数：`/conversations`, `/documents`
- 版本号放 URL 中：`/api/v1/`, `/api/v2/`
- 查询用 GET，创建用 POST，全量更新用 PUT，部分更新用 PATCH，删除用 DELETE
- 分页参数统一：`page` + `page_size`，响应包含 `total`
- 请求/响应使用 Pydantic schema，与数据库 Model 分离

### 流式响应

- 聊天接口使用 SSE（Server-Sent Events）或 WebSocket 实现流式输出
- SSE 格式：`data: {token}\n\n`，结束标记：`data: [DONE]\n\n`
- 前端通过 EventSource 或 fetch 接收流式数据

### 统一响应格式

```python
{
  "code": 0,          # 0 成功，非 0 错误码
  "message": "ok",    # 错误信息
  "data": {...}       # 业务数据
}
```

## 测试规范

- 测试文件与源文件同目录：`rag_service.py` → `test_rag_service.py`
- 使用 pytest + pytest-asyncio
- Mock LLM 响应避免测试依赖外部 API（使用 `pytest-mock` 或 `unittest.mock`）
- RAG 层测试可连接真实 Chroma（测试库），不 mock 向量库
- 测试覆盖核心业务逻辑，不追求 100% 覆盖率
- 测试命名：`test_{函数名}_{场景}_{预期结果}`

```bash
# 常用命令
pytest                          # 运行所有测试
pytest tests/test_rag_service.py  # 运行单个文件
pytest -v -s                    # 详细输出 + 显示 print
pytest --cov=agent --cov=rag    # 生成覆盖率报告
```

## 常用命令

```bash
# 依赖管理
pip install -r requirements.txt
pip freeze > requirements.txt

# 本地运行
streamlit run app.py                    # 当前 Streamlit 版本
uvicorn api.main:app --reload           # 未来 FastAPI 版本

# 前端开发
cd frontend && npm install
cd frontend && npm run dev              # 开发服务器（端口 3000）
cd frontend && npm run build            # 生产构建

# Docker 部署
docker-compose up --build               # 构建并启动
docker-compose down                     # 停止并删除容器

# 测试
pytest
pytest -v -s
pytest --cov

# 代码检查
flake8 .                                # 代码风格检查
black .                                 # 代码格式化
mypy .                                  # 类型检查
```

## Git 工作流

- 分支策略：main (生产) ← develop (开发) ← feature/xxx, fix/xxx, refactor/xxx
- 分支命名：`{type}/{description}`，如 `feature/knowledge-management`, `fix/rag-timeout`
- Commit message 格式：`{type}({scope}): {description}`
  - type: feat / fix / refactor / docs / test / chore / perf
  - 示例：`feat(rag): add reranker for better retrieval`
- 一个 PR 只做一件事，保持 diff 可 review
- PR 合并前确保测试通过

## 安全规范

- **敏感配置**：数据库密码、API Key（DASHSCOPE_API_KEY）不要硬编码，使用环境变量或配置中心
- **不要提交**：`.env` 文件、密钥文件、`chroma_db/` 向量库数据到 Git
- **输入校验**：所有外部输入必须校验（使用 Pydantic schema）
- **Prompt 注入防护**：对用户输入做预处理，过滤/转义特殊指令模式
- **SQL 参数化**：如使用数据库，查询必须参数化，防止注入
- **API 鉴权**：HTTP 接口使用 JWT / 中间件鉴权，区分公开和私有接口
- **日志脱敏**：敏感数据（手机号、身份证、用户原始输入）日志中脱敏处理

## 性能关注点

- **LLM 调用超时**：设置 timeout=30s，避免长时间阻塞
- **流式响应延迟**：p99 首字延迟 < 2s
- **RAG 检索延迟**：p99 < 500ms
- **Token 成本优化**：
  - 简单问答用 qwen-turbo（便宜）
  - 复杂推理用 qwen3-max（贵但准确）
  - 监控每日 Token 消耗，设置预算告警
- **向量库性能**：
  - Chroma 适合开发/小规模（< 100 万向量）
  - 生产大规模迁移到 Milvus
- **缓存策略**：
  - 常见问题的 RAG 检索结果可缓存（Redis）
  - 缓存 TTL 根据知识库更新频率设置

## Codex 交互偏好

- **语言**：用中文沟通
- **风格**：详细分析，解释设计决策的权衡和取舍
- 写代码时先说明设计思路和分层考虑，再给出实现
- 涉及架构决策时，给出至少 2 个方案并对比优劣
- 修改现有代码前先阅读理解，说明改动影响范围
- 不要做超出需求范围的"优化"或"改进"
- 生成代码要符合本项目的分层和命名规范
- 遇到不确定的业务逻辑，先问清楚再实现
