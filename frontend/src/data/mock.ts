import type { ApprovalItem, KnowledgeDocument, MetricSnapshot } from "../types";

export const fallbackDocuments: KnowledgeDocument[] = [
  {
    id: "doc-001",
    title: "产品需求评审流程",
    author: "林知远",
    updated_at: "2026-07-27T10:00:00Z",
    version: 4,
    status: "published",
    visibility: "department",
    department_id: "dept-product",
    tags: ["产品", "流程", "审批"],
    summary: "产品需求评审流程：需求进入评审前，产品经理需要完成背景、目标、范围、验收标准和风险说明。",
    reads: 186,
    content: "需求进入评审前，产品经理需要完成背景、目标、范围、验收标准和风险说明。"
  },
  {
    id: "doc-002",
    title: "知识库检索架构设计",
    author: "周明",
    updated_at: "2026-07-26T09:30:00Z",
    version: 2,
    status: "reviewing",
    visibility: "public",
    department_id: "dept-tech",
    tags: ["技术", "RAG", "架构"],
    summary: "知识库检索架构设计：检索链路采用 Query 改写、语义召回、关键词召回、元数据过滤和 RRF 融合重排序。",
    reads: 142,
    content: "检索链路采用 Query 改写、语义召回、关键词召回、元数据过滤和 RRF 融合重排序。"
  }
];

export const fallbackApprovals: ApprovalItem[] = [
  {
    id: "approval-001",
    document_id: "doc-002",
    title: "知识库检索架构设计",
    submitter: "周明",
    submitted_at: "2026-07-27T13:00:00Z",
    status: "pending",
    summary: "新增多路召回和引用溯源章节。"
  }
];

export const fallbackMetrics: MetricSnapshot = {
  document_total: 2,
  weekly_new: 6,
  active_users: 128,
  pending_approvals: 1,
  trend: [
    { day: "周一", documents: 4, reads: 86 },
    { day: "周二", documents: 7, reads: 104 },
    { day: "周三", documents: 5, reads: 93 },
    { day: "周四", documents: 8, reads: 121 },
    { day: "周五", documents: 9, reads: 138 }
  ],
  top_documents: fallbackDocuments
};
