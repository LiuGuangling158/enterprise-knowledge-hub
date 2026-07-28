import { Archive, ArchiveRestore, ArrowLeft, Eye, FileUp, MessageSquarePlus, Save, Send, SquarePen } from "lucide-react";
import { ChangeEvent, useEffect, useMemo, useState } from "react";
import { api } from "../services/api";
import type { ApprovalItem, DocumentComment, DocumentVersion, KnowledgeDocument, VersionCompareResult } from "../types";

interface EditorProps {
  documentId: string | null;
  onBack: () => void;
  onSaved: (document: KnowledgeDocument) => void;
  onArchived: (document: KnowledgeDocument) => void;
  onRestored: (document: KnowledgeDocument) => void;
  onSubmitted: () => void;
}

export function DocumentEditor({ documentId, onBack, onSaved, onArchived, onRestored, onSubmitted }: EditorProps) {
  const [document, setDocument] = useState<KnowledgeDocument | null>(null);
  const [versions, setVersions] = useState<DocumentVersion[]>([]);
  const [compareLeft, setCompareLeft] = useState(1);
  const [compareRight, setCompareRight] = useState(1);
  const [versionCompare, setVersionCompare] = useState<VersionCompareResult | null>(null);
  const [approvalHistory, setApprovalHistory] = useState<ApprovalItem[]>([]);
  const [comments, setComments] = useState<DocumentComment[]>([]);
  const [title, setTitle] = useState("");
  const [tags, setTags] = useState("");
  const [visibility, setVisibility] = useState<"department" | "public">("department");
  const [content, setContent] = useState("");
  const [summary, setSummary] = useState("更新文档内容");
  const [commentText, setCommentText] = useState("");
  const [mode, setMode] = useState<"edit" | "preview">("edit");
  const [message, setMessage] = useState("");
  const [saving, setSaving] = useState(false);

  function resetEditorState(nextSummary = "创建文档") {
    setDocument(null);
    setVersions([]);
    setCompareLeft(1);
    setCompareRight(1);
    setVersionCompare(null);
    setApprovalHistory([]);
    setComments([]);
    setTitle("");
    setTags("");
    setVisibility("department");
    setContent("");
    setSummary(nextSummary);
    setCommentText("");
  }

  useEffect(() => {
    if (!documentId) {
      resetEditorState();
      return;
    }

    let cancelled = false;
    setMessage("");

    Promise.all([
      api.document(documentId),
      api.versions(documentId),
      api.documentApprovals(documentId),
      api.comments(documentId)
    ]).then(([doc, versionRows, approvalRows, commentRows]) => {
      if (cancelled) return;
      setDocument(doc);
      setVersions(versionRows);
      syncCompareSelection(versionRows, doc.version);
      setApprovalHistory(approvalRows);
      setComments(commentRows);
      setTitle(doc.title);
      setTags(doc.tags.join(", "));
      setVisibility(doc.visibility);
      setContent(doc.content);
      setSummary("更新文档内容");
      setCommentText("");
    }).catch((reason) => {
      if (cancelled) return;
      resetEditorState("更新文档内容");
      setMessage(reason instanceof Error ? reason.message : "文档加载失败");
    });

    return () => {
      cancelled = true;
    };
  }, [documentId]);

  const parsedTags = useMemo(
    () =>
      tags
        .split(",")
        .map((tag) => tag.trim())
        .filter(Boolean),
    [tags]
  );

  function syncCompareSelection(versionRows: DocumentVersion[], fallbackVersion: number) {
    const latest = versionRows[0]?.version ?? fallbackVersion;
    const previous = versionRows[1]?.version ?? latest;
    setCompareLeft(previous);
    setCompareRight(latest);
    setVersionCompare(null);
  }

  async function save() {
    if (document?.status === "archived") {
      setMessage("已归档文档需要恢复后再编辑");
      return;
    }

    setSaving(true);
    setMessage("");
    try {
      const payload = { title, content, tags: parsedTags, visibility, summary };
      const saved = document ? await api.updateDocument(document.id, payload) : await api.createDocument(payload);
      setDocument(saved);
      setMessage("已保存");
      onSaved(saved);
      const [versionRows, approvalRows, commentRows] = await Promise.all([
        api.versions(saved.id),
        api.documentApprovals(saved.id),
        api.comments(saved.id)
      ]);
      setVersions(versionRows);
      syncCompareSelection(versionRows, saved.version);
      setApprovalHistory(approvalRows);
      setComments(commentRows);
    } catch (reason) {
      setMessage(reason instanceof Error ? reason.message : "保存失败");
    } finally {
      setSaving(false);
    }
  }

  async function submitForReview() {
    if (document?.status === "archived") {
      setMessage("已归档文档需要恢复后再提交审批");
      return;
    }

    setSaving(true);
    setMessage("");
    try {
      const payload = { title, content, tags: parsedTags, visibility, summary };
      const current = document ? await api.updateDocument(document.id, payload) : await api.createDocument(payload);
      await api.submitDocument(current.id, summary || "提交审批");
      const reviewingDocument: KnowledgeDocument = { ...current, status: "reviewing" };
      setDocument(reviewingDocument);
      onSaved(reviewingDocument);
      setApprovalHistory(await api.documentApprovals(current.id));
      setMessage("已提交审批");
      onSubmitted();
    } catch (reason) {
      setMessage(reason instanceof Error ? reason.message : "提交审批失败");
    } finally {
      setSaving(false);
    }
  }

  async function archiveCurrentDocument() {
    if (!document) {
      setMessage("请先保存文档再归档");
      return;
    }

    setSaving(true);
    setMessage("");
    try {
      const archived = await api.archiveDocument(document.id);
      setDocument(archived);
      setMessage("文档已归档");
      onArchived(archived);
    } catch (reason) {
      setMessage(reason instanceof Error ? reason.message : "归档失败");
    } finally {
      setSaving(false);
    }
  }

  async function restoreCurrentDocument() {
    if (!document) return;

    setSaving(true);
    setMessage("");
    try {
      const restored = await api.restoreDocument(document.id);
      setDocument(restored);
      setMessage("文档已恢复为草稿");
      onRestored(restored);
    } catch (reason) {
      setMessage(reason instanceof Error ? reason.message : "恢复失败");
    } finally {
      setSaving(false);
    }
  }

  async function compareSelectedVersions() {
    if (!document) {
      setMessage("请先保存文档再对比版本");
      return;
    }

    setSaving(true);
    setMessage("");
    try {
      const result = await api.compareVersions(document.id, compareLeft, compareRight);
      setVersionCompare(result);
    } catch (reason) {
      setMessage(reason instanceof Error ? reason.message : "版本对比失败");
    } finally {
      setSaving(false);
    }
  }

  async function addComment() {
    const content = commentText.trim();
    if (!document) {
      setMessage("请先保存文档再评论");
      return;
    }
    if (document.status === "archived") {
      setMessage("已归档文档不可继续评论");
      return;
    }
    if (!content) {
      setMessage("请输入评论内容");
      return;
    }

    setSaving(true);
    setMessage("");
    try {
      const comment = await api.addComment(document.id, content);
      setComments((items) => [...items, comment]);
      setCommentText("");
      setMessage("评论已添加");
    } catch (reason) {
      setMessage(reason instanceof Error ? reason.message : "评论失败");
    } finally {
      setSaving(false);
    }
  }

  async function uploadFile(event: ChangeEvent<HTMLInputElement>) {
    const file = event.target.files?.[0];
    if (!file) return;

    setSaving(true);
    setMessage("");
    try {
      const uploaded = await api.uploadDocument(file, { visibility, tags: parsedTags });
      setDocument(uploaded);
      setTitle(uploaded.title);
      setTags(uploaded.tags.join(", "));
      setVisibility(uploaded.visibility);
      setContent(uploaded.content);
      setSummary("更新文档内容");
      setMode("edit");
      const [versionRows, approvalRows, commentRows] = await Promise.all([
        api.versions(uploaded.id),
        api.documentApprovals(uploaded.id),
        api.comments(uploaded.id)
      ]);
      setVersions(versionRows);
      syncCompareSelection(versionRows, uploaded.version);
      setApprovalHistory(approvalRows);
      setComments(commentRows);
      setVersionCompare(null);
      setCommentText("");
      setMessage("文件已上传并解析为在线文档");
      onSaved(uploaded);
    } catch (reason) {
      setMessage(reason instanceof Error ? reason.message : "上传解析失败");
    } finally {
      setSaving(false);
      event.target.value = "";
    }
  }

  return (
    <section className="pageStack">
      <div className="pageTitle">
        <div>
          <span className="breadcrumb">文档库 &gt; {document ? document.title : "新建文档"}</span>
          <h1>{document ? "文档编辑" : "新建文档"}</h1>
          <p>编辑 Markdown 内容，保存版本并提交发布审批。</p>
        </div>
        <div className="buttonGroup">
          <button className="secondaryAction" onClick={onBack}>
            <ArrowLeft size={16} />
            <span>返回</span>
          </button>
          <label className="secondaryAction uploadButton">
            <FileUp size={16} />
            <span>上传新文档</span>
            <input type="file" accept=".md,.markdown,.txt,text/markdown,text/plain" onChange={uploadFile} disabled={saving} />
          </label>
          <button className="secondaryAction" onClick={() => setMode(mode === "edit" ? "preview" : "edit")}>
            {mode === "edit" ? <Eye size={16} /> : <SquarePen size={16} />}
            <span>{mode === "edit" ? "预览" : "编辑"}</span>
          </button>
          <button className="primaryAction" onClick={save} disabled={saving}>
            <Save size={16} />
            <span>保存</span>
          </button>
          <button
            className="primaryAction"
            onClick={submitForReview}
            disabled={saving || !title || !content || document?.status === "reviewing" || document?.status === "archived"}
          >
            <Send size={16} />
            <span>提交审批</span>
          </button>
          {document?.status === "archived" ? (
            <button className="secondaryAction" onClick={restoreCurrentDocument} disabled={saving}>
              <ArchiveRestore size={16} />
              <span>恢复</span>
            </button>
          ) : (
            <button
              className="dangerAction"
              onClick={archiveCurrentDocument}
              disabled={!document || saving || document?.status === "reviewing"}
            >
              <Archive size={16} />
              <span>归档</span>
            </button>
          )}
        </div>
      </div>

      {message ? <div className="noticeLine">{message}</div> : null}

      <div className="editorLayout">
        <section className="editorMain">
          <div className="formGrid">
            <label>
              <span>标题</span>
              <input value={title} onChange={(event) => setTitle(event.target.value)} placeholder="输入文档标题" />
            </label>
            <label>
              <span>标签</span>
              <input value={tags} onChange={(event) => setTags(event.target.value)} placeholder="用英文逗号分隔，例如：产品, 流程" />
            </label>
            <label>
              <span>可见范围</span>
              <select value={visibility} onChange={(event) => setVisibility(event.target.value as "department" | "public")}>
                <option value="department">本部门</option>
                <option value="public">全公司</option>
              </select>
            </label>
            <label>
              <span>变更摘要</span>
              <input value={summary} onChange={(event) => setSummary(event.target.value)} />
            </label>
          </div>

          {mode === "edit" ? (
            <textarea className="editorArea" value={content} onChange={(event) => setContent(event.target.value)} placeholder="输入 Markdown 或正文内容" />
          ) : (
            <article className="previewArea">
              <h2>{title || "未命名文档"}</h2>
              <pre>{content || "暂无内容"}</pre>
            </article>
          )}
        </section>

        <aside className="editorSide">
          <div className="sideBlock">
            <h2>文档状态</h2>
            <span className={`status ${document?.status ?? "draft"}`}>{statusText(document?.status ?? "draft")}</span>
            <p>版本：v{document?.version ?? 1}</p>
            <p>阅读：{document?.reads ?? 0}</p>
          </div>
          {document?.source_upload ? (
            <div className="sideBlock">
              <h2>上传来源</h2>
              <p>{document.source_upload.original_filename}</p>
              <p>{formatBytes(document.source_upload.size_bytes)} · {parserText(document.source_upload.parser)}</p>
              <small>{formatDate(document.source_upload.created_at)}</small>
            </div>
          ) : null}
          <div className="sideBlock">
            <h2>自动摘要</h2>
            <p>{document?.summary || "保存后自动生成摘要"}</p>
          </div>
          <div className="sideBlock">
            <h2>审批记录</h2>
            <div className="timelineList">
              {approvalHistory.map((approval) => (
                <article key={approval.id}>
                  <div>
                    <strong>审批节点</strong>
                    <span className={`status ${approval.status}`}>{approvalStatusText(approval.status)}</span>
                  </div>
                  <p>{approval.summary || "无摘要"}</p>
                  {approval.agent_review?.summary ? (
                    <small>Agent 审核：{riskText(approval.agent_review.risk_level)} · {approval.agent_review.summary}</small>
                  ) : null}
                  <small>
                    {approval.submitter} · {formatDate(approval.submitted_at)}
                  </small>
                  {approval.reviewer ? (
                    <small>
                      {approval.reviewer} · {approval.reviewed_at ? formatDate(approval.reviewed_at) : "未完成"}
                    </small>
                  ) : null}
                  {approval.reason ? <p>{approval.reason}</p> : null}
                </article>
              ))}
              {!approvalHistory.length ? <p>暂无审批记录</p> : null}
            </div>
          </div>
          <div className="sideBlock">
            <h2>协作评论</h2>
            <div className="commentList">
              {comments.map((comment) => (
                <article key={comment.id}>
                  <strong>{comment.author}</strong>
                  <small>{formatDate(comment.created_at)}</small>
                  <p>{comment.content}</p>
                </article>
              ))}
              {!comments.length ? <p>暂无评论</p> : null}
            </div>
            <div className="commentForm">
              <textarea
                value={commentText}
                onChange={(event) => setCommentText(event.target.value)}
                placeholder={
                  !document
                    ? "保存文档后可评论"
                    : document.status === "archived"
                      ? "已归档文档不可继续评论"
                      : "写下处理意见或补充说明"
                }
                disabled={!document || saving || document.status === "archived"}
              />
              <button
                className="secondaryAction"
                onClick={addComment}
                disabled={!document || saving || document.status === "archived" || !commentText.trim()}
              >
                <MessageSquarePlus size={16} />
                <span>添加评论</span>
              </button>
            </div>
          </div>
          <div className="sideBlock">
            <h2>版本记录</h2>
            <div className="compareControls">
              <label>
                <span>起始版本</span>
                <select value={compareLeft} onChange={(event) => setCompareLeft(Number(event.target.value))}>
                  {versions.map((version) => (
                    <option value={version.version} key={`left-${version.id}`}>
                      v{version.version}
                    </option>
                  ))}
                </select>
              </label>
              <label>
                <span>目标版本</span>
                <select value={compareRight} onChange={(event) => setCompareRight(Number(event.target.value))}>
                  {versions.map((version) => (
                    <option value={version.version} key={`right-${version.id}`}>
                      v{version.version}
                    </option>
                  ))}
                </select>
              </label>
              <button className="secondaryAction" onClick={compareSelectedVersions} disabled={saving || versions.length < 2}>
                <Eye size={16} />
                <span>对比</span>
              </button>
            </div>
            {versionCompare ? (
              <div className="diffBlock">
                <p>{versionCompare.summary}</p>
                <pre>{versionCompare.diff.length ? versionCompare.diff.slice(0, 24).join("\n") : "两个版本内容一致"}</pre>
              </div>
            ) : versions.length < 2 ? (
              <p>至少两个版本后可对比差异</p>
            ) : null}
            <div className="versionList">
              {versions.map((version) => (
                <article key={version.id}>
                  <strong>v{version.version}</strong>
                  <span>{version.summary || "无摘要"}</span>
                  <small>{version.created_by}</small>
                </article>
              ))}
              {!versions.length ? <p>保存后生成版本记录</p> : null}
            </div>
          </div>
        </aside>
      </div>
    </section>
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

function parserText(parser: string) {
  return {
    markdown: "Markdown 解析",
    plain_text: "文本解析"
  }[parser] ?? parser;
}

function riskText(risk: string) {
  return {
    none: "无风险",
    low: "低风险",
    medium: "中风险",
    high: "高风险"
  }[risk] ?? risk;
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
