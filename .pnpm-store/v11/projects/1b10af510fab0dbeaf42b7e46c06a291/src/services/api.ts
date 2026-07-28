import type {
  AgentCapabilities,
  AdminDepartment,
  AdminOverview,
  AdminUser,
  ApprovalItem,
  ConversationSession,
  DocumentComment,
  DocumentVersion,
  KnowledgeDocument,
  MetricSnapshot,
  OperationLog,
  SearchHit,
  SensitiveScan,
  UserProfile,
  VersionCompareResult
} from "../types";

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? "http://127.0.0.1:8000";
const TOKEN_KEY = "knowledge_platform_token";

let accessToken = localStorage.getItem(TOKEN_KEY);

function authHeaders(): HeadersInit {
  return accessToken ? { Authorization: `Bearer ${accessToken}` } : {};
}

async function request<T>(path: string, options: RequestInit = {}): Promise<T> {
  const headers: HeadersInit = {
    ...authHeaders(),
    ...(options.body ? { "Content-Type": "application/json" } : {}),
    ...(options.headers ?? {})
  };
  const response = await fetch(`${API_BASE_URL}${path}`, { ...options, headers });
  if (!response.ok) {
    if (response.status === 401) api.clearToken();
    const detail = await response.json().catch(() => null);
    throw new Error(detail?.detail ?? `Request failed: ${response.status}`);
  }
  return response.json() as Promise<T>;
}

export const api = {
  getToken: () => accessToken,
  setToken: (token: string) => {
    accessToken = token;
    localStorage.setItem(TOKEN_KEY, token);
  },
  clearToken: () => {
    accessToken = null;
    localStorage.removeItem(TOKEN_KEY);
  },
  login: async (email: string, password: string) => {
    const result = await request<{ access_token: string; user: UserProfile }>("/api/auth/login", {
      method: "POST",
      body: JSON.stringify({ email, password })
    });
    api.setToken(result.access_token);
    return result.user;
  },
  register: async (payload: { name: string; email: string; password: string; department_id: string }) => {
    const result = await request<{ access_token: string; user: UserProfile }>("/api/auth/register", {
      method: "POST",
      body: JSON.stringify(payload)
    });
    api.setToken(result.access_token);
    return result.user;
  },
  me: () => request<UserProfile>("/api/auth/me"),
  documents: (status?: string) =>
    request<KnowledgeDocument[]>(`/api/documents${status ? `?status=${encodeURIComponent(status)}` : ""}`),
  document: (id: string) => request<KnowledgeDocument>(`/api/documents/${id}`),
  createDocument: (payload: {
    title: string;
    content: string;
    tags: string[];
    visibility: "department" | "public";
  }) =>
    request<KnowledgeDocument>("/api/documents", {
      method: "POST",
      body: JSON.stringify(payload)
    }),
  uploadDocument: async (
    file: File,
    options: {
      visibility: "department" | "public";
      tags: string[];
      departmentId?: string | null;
    }
  ) => {
    const params = new URLSearchParams({
      filename: file.name,
      visibility: options.visibility,
      tags: options.tags.join(",")
    });
    if (options.departmentId) params.set("department_id", options.departmentId);

    const response = await fetch(`${API_BASE_URL}/api/documents/upload?${params.toString()}`, {
      method: "POST",
      headers: {
        ...authHeaders(),
        "Content-Type": file.type || "application/octet-stream"
      },
      body: file
    });
    if (!response.ok) {
      if (response.status === 401) api.clearToken();
      const detail = await response.json().catch(() => null);
      throw new Error(detail?.detail ?? `Request failed: ${response.status}`);
    }
    return response.json() as Promise<KnowledgeDocument>;
  },
  updateDocument: (
    id: string,
    payload: {
      title: string;
      content: string;
      tags: string[];
      visibility: "department" | "public";
      summary?: string;
    }
  ) =>
    request<KnowledgeDocument>(`/api/documents/${id}`, {
      method: "PUT",
      body: JSON.stringify(payload)
    }),
  archiveDocument: (id: string) =>
    request<KnowledgeDocument>(`/api/documents/${id}/archive`, {
      method: "POST"
    }),
  restoreDocument: (id: string) =>
    request<KnowledgeDocument>(`/api/documents/${id}/restore`, {
      method: "POST"
    }),
  submitDocument: (id: string, summary: string) =>
    request<ApprovalItem>(`/api/documents/${id}/submit`, {
      method: "POST",
      body: JSON.stringify({ summary })
    }),
  sensitiveScans: (id: string) => request<SensitiveScan[]>(`/api/documents/${id}/sensitive-scans`),
  runSensitiveScan: (id: string) =>
    request<SensitiveScan>(`/api/documents/${id}/sensitive-scan`, {
      method: "POST"
    }),
  versions: (id: string) => request<DocumentVersion[]>(`/api/documents/${id}/versions`),
  compareVersions: (id: string, left: number, right: number) =>
    request<VersionCompareResult>(
      `/api/documents/${id}/versions/compare?left=${encodeURIComponent(left)}&right=${encodeURIComponent(right)}`
    ),
  documentApprovals: (id: string) => request<ApprovalItem[]>(`/api/documents/${id}/approvals`),
  comments: (id: string) => request<DocumentComment[]>(`/api/documents/${id}/comments`),
  addComment: (id: string, content: string) =>
    request<DocumentComment>(`/api/documents/${id}/comments`, {
      method: "POST",
      body: JSON.stringify({ content })
    }),
  approvals: () => request<ApprovalItem[]>("/api/approvals"),
  reviewApproval: (id: string, action: "approve" | "reject", reason?: string) =>
    request<ApprovalItem>(`/api/approvals/${id}/review`, {
      method: "POST",
      body: JSON.stringify({ action, reason })
    }),
  metrics: () => request<MetricSnapshot>("/api/metrics"),
  adminOverview: () => request<AdminOverview>("/api/admin/overview"),
  adminUsers: () => request<AdminUser[]>("/api/admin/users"),
  updateAdminUser: (
    id: string,
    payload: {
      name?: string;
      role?: UserProfile["role"];
      department_id?: string;
    }
  ) =>
    request<AdminUser>(`/api/admin/users/${id}`, {
      method: "PATCH",
      body: JSON.stringify(payload)
    }),
  adminDepartments: () => request<AdminDepartment[]>("/api/admin/departments"),
  adminDocuments: (filters: { status?: string; departmentId?: string } = {}) => {
    const params = new URLSearchParams();
    if (filters.status) params.set("status", filters.status);
    if (filters.departmentId) params.set("department_id", filters.departmentId);
    const suffix = params.toString();
    return request<KnowledgeDocument[]>(`/api/admin/documents${suffix ? `?${suffix}` : ""}`);
  },
  adminApprovals: (status?: string) =>
    request<ApprovalItem[]>(`/api/admin/approvals${status ? `?status=${encodeURIComponent(status)}` : ""}`),
  adminOperationLogs: (filters: { action?: string; resourceType?: string; limit?: number } = {}) => {
    const params = new URLSearchParams();
    if (filters.action) params.set("action", filters.action);
    if (filters.resourceType) params.set("resource_type", filters.resourceType);
    if (filters.limit) params.set("limit", String(filters.limit));
    const suffix = params.toString();
    return request<OperationLog[]>(`/api/admin/operation-logs${suffix ? `?${suffix}` : ""}`);
  },
  adminSensitiveScans: (filters: { riskLevel?: string; limit?: number } = {}) => {
    const params = new URLSearchParams();
    if (filters.riskLevel) params.set("risk_level", filters.riskLevel);
    if (filters.limit) params.set("limit", String(filters.limit));
    const suffix = params.toString();
    return request<SensitiveScan[]>(`/api/admin/sensitive-scans${suffix ? `?${suffix}` : ""}`);
  },
  agentCapabilities: () => request<AgentCapabilities>("/api/agents/capabilities"),
  conversations: () => request<ConversationSession[]>("/api/conversations"),
  conversation: (sessionId: string) => request<ConversationSession>(`/api/conversations/${sessionId}`),
  search: (query: string) =>
    request<{ results: SearchHit[]; retrieval_meta?: Record<string, unknown> }>(`/api/search?q=${encodeURIComponent(query)}`),
  ask: async (
    sessionId: string,
    question: string,
    onDelta: (text: string) => void,
    onMeta: (payload: Record<string, unknown>) => void
  ) => {
    const response = await fetch(`${API_BASE_URL}/api/ask`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        ...authHeaders()
      },
      body: JSON.stringify({ question, session_id: sessionId })
    });

    if (!response.ok || !response.body) {
      throw new Error(`Streaming request failed: ${response.status}`);
    }

    const reader = response.body.getReader();
    const decoder = new TextDecoder();
    let buffer = "";

    while (true) {
      const { value, done } = await reader.read();
      if (done) break;
      buffer += decoder.decode(value, { stream: true });
      const events = buffer.split("\n\n");
      buffer = events.pop() ?? "";

      for (const event of events) {
        const eventName = event.match(/^event:\s*(.+)$/m)?.[1];
        const dataText = event.match(/^data:\s*(.+)$/m)?.[1];
        if (!eventName || !dataText) continue;
        const data = JSON.parse(dataText);
        if (eventName === "answer_delta") onDelta(data.text);
        if (eventName !== "answer_delta") onMeta({ event: eventName, ...data });
      }
    }
  }
};
