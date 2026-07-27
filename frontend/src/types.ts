export type ViewKey = "dashboard" | "documents" | "approvals" | "qa" | "analytics" | "admin" | "editor";

export type DocumentStatus = "draft" | "reviewing" | "published" | "rejected" | "archived";

export interface UserProfile {
  id: string;
  tenant_id: string;
  department_id: string;
  department: string;
  email: string;
  name: string;
  role: "admin" | "editor" | "member";
}

export interface KnowledgeDocument {
  id: string;
  tenant_id?: string;
  department_id: string;
  department?: string;
  title: string;
  author: string;
  author_id?: string;
  created_at?: string;
  updated_at: string;
  version: number;
  status: DocumentStatus;
  visibility: "department" | "public";
  tags: string[];
  reads: number;
  content: string;
}

export interface ApprovalItem {
  id: string;
  document_id: string;
  title: string;
  submitter: string;
  submitted_at: string;
  status: "pending" | "approved" | "rejected";
  summary: string;
  reviewer?: string | null;
  reason?: string | null;
  reviewed_at?: string | null;
}

export interface DocumentVersion {
  id: string;
  document_id: string;
  version: number;
  title: string;
  summary: string;
  created_by: string;
  created_at: string;
}

export interface DocumentComment {
  id: string;
  document_id: string;
  author: string;
  author_id: string;
  content: string;
  created_at: string;
}

export interface ConversationMessage {
  id: string;
  session_id: string;
  role: "user" | "assistant";
  content: string;
  meta: Record<string, unknown>;
  created_at: string;
}

export interface ConversationSession {
  id: string;
  tenant_id: string;
  user_id: string;
  title: string;
  created_at: string;
  updated_at: string;
  messages: ConversationMessage[];
}

export interface MetricSnapshot {
  document_total: number;
  weekly_new: number;
  active_users: number;
  pending_approvals: number;
  trend: Array<{ day: string; documents: number; reads: number }>;
  top_documents: KnowledgeDocument[];
}

export interface SearchHit {
  document_id: string;
  title: string;
  section: string;
  snippet: string;
  score: number;
  citation: string;
}
