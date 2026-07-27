# 企业内部知识库与文档协作平台

基于规划文档搭建的全栈项目，当前已补齐 V1 主链路，并按版本规划推进到 V2：登录鉴权、文档创建/编辑/保存、上传解析、提交审批、文档级审批轨迹、协作评论、归档恢复、审批通过/驳回、基础搜索、权限隔离入口、RAG 问答、对话历史、结构化引用来源、自动摘要与文档版本比较。

## 技术栈

- 前端：React + TypeScript + Vite
- 后端：FastAPI
- 数据层：PostgreSQL、Redis、ChromaDB、MinIO
- 智能层：LangGraph 预留接口、RAG 检索管道、Agent 工具协议

默认本地开发使用 `backend/knowledge_v1.db`。配置 `DATABASE_URL=postgresql+psycopg://knowledge:knowledge@localhost:5432/knowledge_platform` 后可切换到 PostgreSQL。

## 目录

```text
frontend/                  React 控制台
backend/                   FastAPI 服务与 Agent/RAG 模块
db/                        数据库初始化脚本
docker-compose.yml         本地依赖编排
tech_decisions.md          技术决策记录
```

## 本地启动

后端：

```bash
cd backend
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
uvicorn main:app --reload --port 8000
```

前端：

```bash
cd frontend
npm install
npm run dev
```

依赖服务：

```bash
docker compose up -d
```

前端默认请求 `http://127.0.0.1:8000`。可在 `frontend/.env` 中配置 `VITE_API_BASE_URL`。

演示账号：

```text
admin@example.com / 123456
product@example.com / 123456
tech@example.com / 123456
```

## 当前范围

- 登录页、控制台首页、文档库、文档编辑页、审批中心、数据看板、知识问答浮层
- 文档新建、编辑、版本记录、上传解析、协作评论、归档恢复、提交审批、审批通过/驳回
- 文档列表、详情、基础全文搜索、审批列表、文档级审批轨迹 API
- Query 改写、多路召回、引用输出的轻量实现
- SSE 流式问答输出
- 问答对话历史持久化与用户级隔离
- RAG 引用来源结构化输出，包含文档、版本、章节、片段和分数
- 文档创建/更新时自动生成摘要
- 文档版本差异比较，支持增删行统计和 diff 展示
- 多租户与部门隔离字段设计
- Agent Trace、预算管理、MCP/A2A 协议骨架

## 后续迭代

- 引入 Alembic 管理正式迁移
- 接入 LangGraph 与真实 LLM tool calling
- 接入 ChromaDB/pgvector、BM25 与重排序模型
- 完善 JWT、RLS、文档级 ACL 与审计日志
- 补充单元测试和集成测试
