import { ArrowLeft, Eye, FileUp, MessageSquarePlus, Save, Send, SquarePen } from "lucide-react";
import { ChangeEvent, useEffect, useMemo, useState } from "react";
import { api } from "../services/api";
import type { ApprovalItem, DocumentComment, DocumentVersion, KnowledgeDocument } from "../types";

interface EditorProps {
  documentId: string | null;
  onBack: () => void;
  onSaved: (document: KnowledgeDocument) => void;
  onSubmitted: () => void;
}

export function DocumentEditor({ documentId, onBack, onSaved, onSubmitted }: EditorProps) {
  const [document, setDocument] = useState<KnowledgeDocument | null>(null);
  const [versions, setVersions] = useState<DocumentVersion[]>([]);
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

  useEffect(() => {
    if (!documentId) {
      setDocument(null);
      setVersions([]);
      setApprovalHistory([]);
      setComments([]);
      setTitle("");
      setTags("");
      setVisibility("department");
      setContent("");
      setSummary("创建文档");
      setCommentText("");
      return;
    }

    Promise.all([
      api.document(documentId),
      api.versions(documentId),
      api.documentApprovals(documentId),
      api.comments(documentId)
    ]).then(([doc, versionRows, approvalRows, commentRows]) => {
      setDocument(doc);
      setVersions(versionRows);
      setApprovalHistory(approvalRows);
      setComments(commentRows);
      setTitle(doc.title);
      setTags(doc.tags.join(", "));
      setVisibility(doc.visibility);
      setContent(doc.content);
      setSummary("更新文档内容");
      setCommentText("");
    });
  }, [documentId]);

  const parsedTags = useMemo(
    () =>
      tags
        .split(",")
        .map((tag) => tag.trim())
        .filter(Boolean),
    [tags]
  );

  async function save() {
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
      setApprovalHistory(approvalRows);
      setComments(commentRows);
    } catch (reason) {
      setMessage(reason instanceof Error ? reason.message : "保存失败");
    } finally {
      setSaving(false);
    }
  }

  async function submitForReview() {
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

  async function addComment() {
    const content = commentText.trim();
    if (!document) {
      setMessage("请先保存文档再评论");
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

  function loadFile(event: ChangeEvent<HTMLInputElement>) {
    const file = event.target.files?.[0];
    if (!file) return;
    file.text().then((text) => {
      setContent(text);
      if (!title) setTitle(file.name.replace(/\.(md|markdown|txt)$/i, ""));
      setSummary("上传解析文档");
    });
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
            <span>上传解析</span>
            <input type="file" accept=".md,.markdown,.txt,text/markdown,text/plain" onChange={loadFile} />
          </label>
          <button className="secondaryAction" onClick={() => setMode(mode === "edit" ? "preview" : "edit")}>
            {mode === "edit" ? <Eye size={16} /> : <SquarePen size={16} />}
            <span>{mode === "edit" ? "预览" : "编辑"}</span>
          </button>
          <button className="primaryAction" onClick={save} disabled={saving}>
            <Save size={16} />
            <span>保存</span>
          </button>
          <button className="primaryAction" onClick={submitForReview} disabled={!title || !content || document?.status === "reviewing"}>
            <Send size={16} />
            <span>提交审批</span>
          </button>
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
                placeholder={document ? "写下处理意见或补充说明" : "保存文档后可评论"}
                disabled={!document || saving}
              />
              <button className="secondaryAction" onClick={addComment} disabled={!document || saving || !commentText.trim()}>
                <MessageSquarePlus size={16} />
                <span>添加评论</span>
              </button>
            </div>
          </div>
          <div className="sideBlock">
            <h2>版本记录</h2>
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
    rejected: "已驳回"
  }[status];
}

function approvalStatusText(status: ApprovalItem["status"]) {
  return {
    pending: "待处理",
    approved: "已通过",
    rejected: "已驳回"
  }[status];
}

function formatDate(value: string) {
  return new Intl.DateTimeFormat("zh-CN", {
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit"
  }).format(new Date(value));
}
