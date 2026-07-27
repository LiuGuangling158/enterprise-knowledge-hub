# 技术决策记录

## ADR-001: 开发期向量库选择 ChromaDB

- 背景：需要快速搭建文档语义检索能力。
- 选项：ChromaDB、FAISS、Milvus、pgvector。
- 选择：开发期使用 ChromaDB，生产期演进为 FAISS 或 PostgreSQL pgvector。
- 理由：ChromaDB 本地启动成本低，适合 V1/V2 快速迭代；pgvector 便于和业务数据统一治理；Milvus 对当前规模偏重。
- 取舍：优先保证开发效率，百万级检索性能优化放到 V3/V4。

## ADR-002: 前端状态管理先使用组件状态

- 背景：V1 页面以控制台、文档列表、审批和浮层问答为主。
- 选项：Redux、Zustand、React Context、组件状态。
- 选择：组件状态加服务层封装。
- 理由：当前跨页面共享状态较少，先保持实现简单；当会话、权限、通知中心复杂后再引入 Zustand。
- 取舍：减少早期抽象，保留未来迁移空间。

## ADR-003: 流式问答使用 SSE

- 背景：知识问答需要实时展示 Agent 执行过程。
- 选项：SSE、WebSocket、轮询。
- 选择：SSE。
- 理由：问答过程主要是服务端向前端单向推送，SSE 简单、可观测、易调试。
- 取舍：不适合高频双向协作场景，如后续需要多人实时编辑可补充 WebSocket。

## ADR-004: 多 Agent 编排采用 Orchestrator-Worker

- 背景：不同问题需要路由到检索、问答、审核、分析等能力。
- 选项：Orchestrator-Worker、Pipeline、群聊式 Agent。
- 选择：Orchestrator-Worker 为主，Pipeline 为辅。
- 理由：企业知识问答更强调可控、可追踪、可降级；Orchestrator-Worker 更利于权限、预算和 Trace 管理。
- 取舍：牺牲部分自由协作能力，换取稳定性和工程可解释性。

## ADR-005: V1 本地开发提供 SQLite 默认持久化

- 背景：规划中的生产数据层是 PostgreSQL，但 Windows 本地开发和面试演示需要低门槛启动。
- 选项：强制 PostgreSQL、SQLite 默认加 PostgreSQL 可配置、纯内存数据。
- 选择：SQLAlchemy 统一数据访问，默认 SQLite，本地或生产配置 `DATABASE_URL=postgresql+psycopg://...` 后切换 PostgreSQL。
- 理由：V1 重点是跑通登录、文档、审批、搜索主链路；SQLite 避免 Docker 或数据库服务不可用时阻塞演示。
- 取舍：SQLite 不代表最终生产形态，正式部署时仍使用 PostgreSQL，并补 Alembic 迁移和 RLS 策略。
