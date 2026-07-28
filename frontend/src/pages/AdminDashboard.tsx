import {
  Archive,
  ArchiveRestore,
  Building2,
  CheckCircle2,
  FileText,
  RefreshCcw,
  Save,
  ScrollText,
  ShieldAlert,
  ShieldCheck,
  UploadCloud,
  Users
} from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import { api } from "../services/api";
import type {
  AdminDepartment,
  AdminOverview,
  AdminUser,
  ApprovalItem,
  KnowledgeDocument,
  OperationLog,
  SensitiveScan,
  UserProfile
} from "../types";

type AdminTab = "overview" | "users" | "departments" | "documents" | "approvals" | "logs" | "sensitive";

const emptyOverview: AdminOverview = {
  metrics: {
    user_total: 0,
    department_total: 0,
    document_total: 0,
    upload_total: 0,
    pending_approvals: 0,
    published_documents: 0,
    archived_documents: 0,
    weekly_new_documents: 0,
    weekly_uploads: 0,
    total_reads: 0,
    operation_log_total: 0,
    sensitive_risk_total: 0
  },
  status_breakdown: [],
  department_breakdown: [],
  recent_documents: [],
  recent_approvals: [],
  recent_uploads: []
};

interface AdminDashboardProps {
  currentUser: UserProfile;
  query: string;
  onOpenDocument: (id: string) => void;
  onDataChanged: () => void | Promise<void>;
}

export function AdminDashboard({ currentUser, query, onOpenDocument, onDataChanged }: AdminDashboardProps) {
  const [tab, setTab] = useState<AdminTab>("overview");
  const [overview, setOverview] = useState<AdminOverview>(emptyOverview);
  const [users, setUsers] = useState<AdminUser[]>([]);
  const [departments, setDepartments] = useState<AdminDepartment[]>([]);
  const [documents, setDocuments] = useState<KnowledgeDocument[]>([]);
  const [approvals, setApprovals] = useState<ApprovalItem[]>([]);
  const [operationLogs, setOperationLogs] = useState<OperationLog[]>([]);
  const [sensitiveScans, setSensitiveScans] = useState<SensitiveScan[]>([]);
  const [documentStatus, setDocumentStatus] = useState("all");
  const [departmentFilter, setDepartmentFilter] = useState("");
  const [loading, setLoading] = useState(false);
  const [savingId, setSavingId] = useState<string | null>(null);
  const [message, setMessage] = useState("");

  async function loadAdmin() {
    if (currentUser.role !== "admin") return;
    setLoading(true);
    setMessage("");
    try {
      const [overviewRows, userRows, departmentRows, documentRows, approvalRows, logRows, scanRows] = await Promise.all([
        api.adminOverview(),
        api.adminUsers(),
        api.adminDepartments(),
        api.adminDocuments(),
        api.adminApprovals(),
        api.adminOperationLogs({ limit: 100 }),
        api.adminSensitiveScans({ limit: 100 })
      ]);
      setOverview(overviewRows);
      setUsers(userRows);
      setDepartments(departmentRows);
      setDocuments(documentRows);
      setApprovals(approvalRows);
      setOperationLogs(logRows);
      setSensitiveScans(scanRows);
    } catch (reason) {
      setMessage(reason instanceof Error ? reason.message : "管理后台加载失败");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    loadAdmin();
  }, [currentUser.role]);

  const normalizedQuery = query.trim().toLowerCase();
  const filteredUsers = useMemo(
    () =>
      users.filter((item) =>
        `${item.name} ${item.email} ${item.department} ${item.role}`.toLowerCase().includes(normalizedQuery)
      ),
    [normalizedQuery, users]
  );
  const filteredDocuments = useMemo(
    () =>
      documents.filter((item) => {
        if (documentStatus !== "all" && item.status !== documentStatus) return false;
        if (departmentFilter && item.department_id !== departmentFilter) return false;
        return `${item.title} ${item.author} ${item.department ?? ""} ${item.tags.join(" ")}`
          .toLowerCase()
          .includes(normalizedQuery);
      }),
    [departmentFilter, documentStatus, documents, normalizedQuery]
  );
  const filteredApprovals = useMemo(
    () =>
      approvals.filter((item) =>
        `${item.title} ${item.submitter} ${item.status} ${item.summary}`.toLowerCase().includes(normalizedQuery)
      ),
    [approvals, normalizedQuery]
  );
  const filteredLogs = useMemo(
    () =>
      operationLogs.filter((item) =>
        `${item.actor ?? ""} ${item.actor_email ?? ""} ${item.action} ${item.resource_type} ${item.summary}`
          .toLowerCase()
          .includes(normalizedQuery)
      ),
    [normalizedQuery, operationLogs]
  );
  const filteredSensitiveScans = useMemo(
    () =>
      sensitiveScans.filter((item) =>
        `${item.document_title} ${item.scanner ?? ""} ${item.risk_level} ${item.summary}`
          .toLowerCase()
          .includes(normalizedQuery)
      ),
    [normalizedQuery, sensitiveScans]
  );

  if (currentUser.role !== "admin") {
    return (
      <section className="pageStack">
        <div className="pageTitle">
          <div>
            <span className="breadcrumb">管理后台</span>
            <h1>无权访问</h1>
            <p>当前账号不是管理员。</p>
          </div>
        </div>
      </section>
    );
  }

  async function saveUser(user: AdminUser) {
    setSavingId(user.id);
    setMessage("");
    try {
      const updated = await api.updateAdminUser(user.id, {
        name: user.name,
        role: user.role,
        department_id: user.department_id
      });
      setUsers((current) => current.map((item) => (item.id === updated.id ? updated : item)));
      setMessage("用户已更新");
      await Promise.all([loadAdmin(), onDataChanged()]);
    } catch (reason) {
      setMessage(reason instanceof Error ? reason.message : "用户更新失败");
    } finally {
      setSavingId(null);
    }
  }

  async function changeDocumentStatus(document: KnowledgeDocument) {
    setSavingId(document.id);
    setMessage("");
    try {
      if (document.status === "archived") {
        await api.restoreDocument(document.id);
        setMessage("文档已恢复");
      } else {
        await api.archiveDocument(document.id);
        setMessage("文档已归档");
      }
      await Promise.all([loadAdmin(), onDataChanged()]);
    } catch (reason) {
      setMessage(reason instanceof Error ? reason.message : "文档状态更新失败");
    } finally {
      setSavingId(null);
    }
  }

  async function reviewApproval(item: ApprovalItem, action: "approve" | "reject") {
    setSavingId(item.id);
    setMessage("");
    try {
      await api.reviewApproval(item.id, action, action === "approve" ? "管理员后台通过" : "管理员后台驳回");
      setMessage(action === "approve" ? "审批已通过" : "审批已驳回");
      await Promise.all([loadAdmin(), onDataChanged()]);
    } catch (reason) {
      setMessage(reason instanceof Error ? reason.message : "审批处理失败");
    } finally {
      setSavingId(null);
    }
  }

  return (
    <section className="pageStack">
      <div className="pageTitle">
        <div>
          <span className="breadcrumb">管理后台</span>
          <h1>管理后台</h1>
          <p>用户、团队、文档、审批和上传记录。</p>
        </div>
        <button className="secondaryAction" onClick={() => loadAdmin()} disabled={loading}>
          <RefreshCcw size={16} />
          <span>刷新</span>
        </button>
      </div>

      {message ? <div className="noticeLine">{message}</div> : null}

      <div className="adminTabs segmented">
        {[
          ["overview", "概览"],
          ["users", "用户"],
          ["departments", "部门"],
          ["documents", "文档"],
          ["approvals", "审批"],
          ["logs", "日志"],
          ["sensitive", "敏感"]
        ].map(([key, label]) => (
          <button key={key} className={tab === key ? "selected" : ""} onClick={() => setTab(key as AdminTab)}>
            {label}
          </button>
        ))}
      </div>

      {tab === "overview" ? <OverviewPanel overview={overview} /> : null}

      {tab === "users" ? (
        <section className="panelBlock">
          <div className="sectionHeader">
            <h2>用户管理</h2>
            <span>{filteredUsers.length} 人</span>
          </div>
          <div className="adminTableWrap">
            <table className="adminTable">
              <thead>
                <tr>
                  <th>用户</th>
                  <th>部门</th>
                  <th>角色</th>
                  <th>贡献</th>
                  <th>会话</th>
                  <th>操作</th>
                </tr>
              </thead>
              <tbody>
                {filteredUsers.map((user) => (
                  <tr key={user.id}>
                    <td>
                      <input
                        value={user.name}
                        onChange={(event) => updateUserDraft(user.id, "name", event.target.value)}
                      />
                      <small>{user.email}</small>
                    </td>
                    <td>
                      <select
                        value={user.department_id}
                        onChange={(event) => updateUserDraft(user.id, "department_id", event.target.value)}
                      >
                        {departments.map((department) => (
                          <option value={department.id} key={department.id}>
                            {department.name}
                          </option>
                        ))}
                      </select>
                    </td>
                    <td>
                      <select value={user.role} onChange={(event) => updateUserDraft(user.id, "role", event.target.value)}>
                        <option value="admin">管理员</option>
                        <option value="editor">编辑</option>
                        <option value="member">成员</option>
                      </select>
                    </td>
                    <td>{user.document_count} 文档 / {user.submitted_approval_count} 提交</td>
                    <td>{user.conversation_count}</td>
                    <td>
                      <button className="secondaryAction" onClick={() => saveUser(user)} disabled={savingId === user.id}>
                        <Save size={15} />
                        <span>保存</span>
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>
      ) : null}

      {tab === "departments" ? (
        <section className="panelBlock">
          <div className="sectionHeader">
            <h2>部门空间</h2>
            <span>{departments.length} 个</span>
          </div>
          <div className="departmentGrid">
            {departments.map((department) => (
              <article className="departmentItem" key={department.id}>
                <div>
                  <strong>{department.name}</strong>
                  <span>{department.id}</span>
                </div>
                <div className="departmentStats">
                  <span>{department.user_count} 用户</span>
                  <span>{department.document_count} 文档</span>
                  <span>{department.pending_approval_count} 待审批</span>
                  <span>{department.upload_count} 上传</span>
                </div>
              </article>
            ))}
          </div>
        </section>
      ) : null}

      {tab === "documents" ? (
        <section className="panelBlock">
          <div className="sectionHeader adminSectionHeader">
            <div>
              <h2>文档治理</h2>
              <span>{filteredDocuments.length} 份</span>
            </div>
            <div className="adminFilters">
              <select value={documentStatus} onChange={(event) => setDocumentStatus(event.target.value)}>
                <option value="all">全部状态</option>
                <option value="published">已发布</option>
                <option value="reviewing">审核中</option>
                <option value="draft">草稿</option>
                <option value="rejected">已驳回</option>
                <option value="archived">已归档</option>
              </select>
              <select value={departmentFilter} onChange={(event) => setDepartmentFilter(event.target.value)}>
                <option value="">全部部门</option>
                {departments.map((department) => (
                  <option value={department.id} key={department.id}>
                    {department.name}
                  </option>
                ))}
              </select>
            </div>
          </div>
          <div className="adminList">
            {filteredDocuments.map((document) => (
              <article className="adminRecord" key={document.id}>
                <div>
                  <strong>{document.title}</strong>
                  <span>{document.department ?? document.department_id} · {document.author} · v{document.version}</span>
                  <p>{document.source_upload ? `来源：${document.source_upload.original_filename}` : document.summary}</p>
                </div>
                <div className="recordActions">
                  <span className={`status ${document.status}`}>{statusText(document.status)}</span>
                  <button className="secondaryAction" onClick={() => onOpenDocument(document.id)}>
                    <FileText size={15} />
                    <span>打开</span>
                  </button>
                  <button
                    className={document.status === "archived" ? "secondaryAction" : "dangerAction"}
                    onClick={() => changeDocumentStatus(document)}
                    disabled={savingId === document.id || document.status === "reviewing"}
                  >
                    {document.status === "archived" ? <ArchiveRestore size={15} /> : <Archive size={15} />}
                    <span>{document.status === "archived" ? "恢复" : "归档"}</span>
                  </button>
                </div>
              </article>
            ))}
            {!filteredDocuments.length ? <p className="emptyText">暂无匹配文档</p> : null}
          </div>
        </section>
      ) : null}

      {tab === "approvals" ? (
        <section className="panelBlock">
          <div className="sectionHeader">
            <h2>审批管理</h2>
            <span>{filteredApprovals.length} 条</span>
          </div>
          <div className="adminList">
            {filteredApprovals.map((item) => (
              <article className="adminRecord" key={item.id}>
                <div>
                  <strong>{item.title}</strong>
                  <span>{item.submitter} · {formatDate(item.submitted_at)}</span>
                  <p>{item.summary || "无摘要"}</p>
                  {item.agent_review?.summary ? (
                    <div className={`agentReview compact ${item.agent_review.risk_level}`}>
                      <span>Agent 审核：{riskText(item.agent_review.risk_level)} · {item.agent_review.summary}</span>
                    </div>
                  ) : null}
                </div>
                <div className="recordActions">
                  <span className={`status ${item.status}`}>{approvalStatusText(item.status)}</span>
                  {item.status === "pending" ? (
                    <>
                      <button className="primaryAction" onClick={() => reviewApproval(item, "approve")} disabled={savingId === item.id}>
                        <CheckCircle2 size={15} />
                        <span>通过</span>
                      </button>
                      <button className="dangerAction" onClick={() => reviewApproval(item, "reject")} disabled={savingId === item.id}>
                        <span>驳回</span>
                      </button>
                    </>
                  ) : null}
                </div>
              </article>
            ))}
            {!filteredApprovals.length ? <p className="emptyText">暂无匹配审批</p> : null}
          </div>
        </section>
      ) : null}

      {tab === "logs" ? (
        <section className="panelBlock">
          <div className="sectionHeader">
            <h2>操作日志</h2>
            <span>{filteredLogs.length} 条</span>
          </div>
          <div className="adminList">
            {filteredLogs.map((item) => (
              <article className="adminRecord" key={item.id}>
                <div>
                  <strong>{actionText(item.action)}</strong>
                  <span>{item.actor ?? "系统"} · {formatDate(item.created_at)}</span>
                  <p>{item.summary || "无摘要"}</p>
                  <small className="metadataLine">{resourceText(item.resource_type)}：{item.resource_id ?? "-"}</small>
                </div>
                <div className="recordActions">
                  <span className="status draft">{item.action}</span>
                </div>
              </article>
            ))}
            {!filteredLogs.length ? <p className="emptyText">暂无匹配日志</p> : null}
          </div>
        </section>
      ) : null}

      {tab === "sensitive" ? (
        <section className="panelBlock">
          <div className="sectionHeader">
            <h2>敏感检测</h2>
            <span>{filteredSensitiveScans.length} 条</span>
          </div>
          <div className="adminList">
            {filteredSensitiveScans.map((item) => (
              <article className="adminRecord" key={item.id}>
                <div>
                  <strong>{item.document_title}</strong>
                  <span>{item.scanner ?? "系统"} · {formatDate(item.created_at)}</span>
                  <p>{item.summary}</p>
                  {item.findings.length ? (
                    <div className="riskList compactRiskList">
                      {item.findings.slice(0, 4).map((finding, index) => (
                        <span key={`${item.id}-${index}`}>{finding.term ?? finding.message}</span>
                      ))}
                    </div>
                  ) : null}
                </div>
                <div className="recordActions">
                  <span className={`status ${item.status === "needs_attention" ? "rejected" : "approved"}`}>
                    {riskText(item.risk_level)} · {item.finding_count} 项
                  </span>
                  <button className="secondaryAction" onClick={() => onOpenDocument(item.document_id)}>
                    <FileText size={15} />
                    <span>打开</span>
                  </button>
                </div>
              </article>
            ))}
            {!filteredSensitiveScans.length ? <p className="emptyText">暂无匹配检测记录</p> : null}
          </div>
        </section>
      ) : null}
    </section>
  );

  function updateUserDraft(id: string, field: "name" | "department_id" | "role", value: string) {
    setUsers((current) =>
      current.map((item) =>
        item.id === id
          ? {
              ...item,
              [field]: value
            }
          : item
      )
    );
  }
}

function OverviewPanel({ overview }: { overview: AdminOverview }) {
  return (
    <>
      <div className="metricGrid adminMetricGrid">
        <AdminMetric label="用户" value={overview.metrics.user_total} Icon={Users} />
        <AdminMetric label="部门" value={overview.metrics.department_total} Icon={Building2} />
        <AdminMetric label="文档" value={overview.metrics.document_total} Icon={FileText} />
        <AdminMetric label="上传" value={overview.metrics.upload_total} Icon={UploadCloud} />
        <AdminMetric label="待审批" value={overview.metrics.pending_approvals} Icon={ShieldCheck} />
        <AdminMetric label="待处理风险" value={overview.metrics.sensitive_risk_total} Icon={ShieldAlert} />
        <AdminMetric label="操作日志" value={overview.metrics.operation_log_total} Icon={ScrollText} />
      </div>

      <div className="twoColumn">
        <section className="panelBlock">
          <div className="sectionHeader">
            <h2>部门分布</h2>
            <span>{overview.department_breakdown.length} 个部门</span>
          </div>
          <div className="documentRows">
            {overview.department_breakdown.map((department) => (
              <article className="rowItem" key={department.id}>
                <div>
                  <strong>{department.name}</strong>
                  <span>{department.user_count} 用户 · {department.document_count} 文档</span>
                </div>
                <span className="status pending">{department.pending_approval_count} 待审</span>
              </article>
            ))}
          </div>
        </section>

        <section className="panelBlock">
          <div className="sectionHeader">
            <h2>最近上传</h2>
            <span>{overview.metrics.weekly_uploads} 本周</span>
          </div>
          <div className="documentRows">
            {overview.recent_uploads.map((upload) => (
              <article className="rowItem" key={upload.id}>
                <div>
                  <strong>{upload.original_filename}</strong>
                  <span>{upload.department} · {upload.uploader}</span>
                </div>
                <span>{formatBytes(upload.size_bytes)}</span>
              </article>
            ))}
            {!overview.recent_uploads.length ? <p className="emptyText">暂无上传记录</p> : null}
          </div>
        </section>
      </div>
    </>
  );
}

function AdminMetric({ label, value, Icon }: { label: string; value: number; Icon: typeof Users }) {
  return (
    <article className="metricItem">
      <Icon size={20} />
      <span>{label}</span>
      <strong>{value}</strong>
    </article>
  );
}

function statusText(status: KnowledgeDocument["status"]) {
  return {
    draft: "草稿",
    reviewing: "审核中",
    published: "已发布",
    rejected: "已驳回",
    archived: "已归档"
  }[status];
}

function approvalStatusText(status: ApprovalItem["status"]) {
  return {
    pending: "待处理",
    approved: "已通过",
    rejected: "已驳回"
  }[status];
}

function riskText(risk: string) {
  return {
    none: "无风险",
    low: "低风险",
    medium: "中风险",
    high: "高风险"
  }[risk] ?? risk;
}

function actionText(action: string) {
  return {
    "auth.login": "用户登录",
    "auth.register": "用户注册",
    "document.create": "创建文档",
    "document.upload": "上传文档",
    "document.update": "更新文档",
    "document.archive": "归档文档",
    "document.restore": "恢复文档",
    "approval.submit": "提交审批",
    "approval.review": "处理审批",
    "comment.create": "添加评论",
    "qa.ask": "知识问答",
    "sensitive.scan": "敏感检测",
    "admin.user.update": "更新用户"
  }[action] ?? action;
}

function resourceText(resourceType: string) {
  return {
    user: "用户",
    document: "文档",
    approval: "审批",
    comment: "评论",
    conversation: "会话"
  }[resourceType] ?? resourceType;
}

function formatBytes(bytes: number) {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / 1024 / 1024).toFixed(1)} MB`;
}

function formatDate(value: string) {
  return new Intl.DateTimeFormat("zh-CN", {
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit"
  }).format(new Date(value));
}
