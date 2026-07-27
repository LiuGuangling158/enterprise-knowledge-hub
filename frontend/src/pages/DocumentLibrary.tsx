import { Archive, ArchiveRestore, Edit3, Grid2X2, ListFilter, Rows3, Save } from "lucide-react";
import { useState } from "react";
import type { DocumentStatus, KnowledgeDocument } from "../types";

export function DocumentLibrary({
  documents,
  archivedDocuments,
  onCreate,
  onEdit,
  onArchive,
  onRestore
}: {
  documents: KnowledgeDocument[];
  archivedDocuments: KnowledgeDocument[];
  onCreate: () => void;
  onEdit: (id: string) => void;
  onArchive: (id: string) => Promise<void>;
  onRestore: (id: string) => Promise<void>;
}) {
  const [display, setDisplay] = useState<"list" | "grid">("list");
  const [status, setStatus] = useState<"all" | DocumentStatus>("all");
  const [busyId, setBusyId] = useState<string | null>(null);
  const [message, setMessage] = useState("");
  const sourceDocuments = status === "archived" ? archivedDocuments : documents;
  const filtered =
    status === "all" || status === "archived"
      ? sourceDocuments
      : sourceDocuments.filter((document) => document.status === status);

  async function archiveDocument(id: string) {
    setBusyId(id);
    setMessage("");
    try {
      await onArchive(id);
      setMessage("文档已归档");
    } catch (reason) {
      setMessage(reason instanceof Error ? reason.message : "归档失败");
    } finally {
      setBusyId(null);
    }
  }

  async function restoreDocument(id: string) {
    setBusyId(id);
    setMessage("");
    try {
      await onRestore(id);
      setMessage("文档已恢复为草稿");
    } catch (reason) {
      setMessage(reason instanceof Error ? reason.message : "恢复失败");
    } finally {
      setBusyId(null);
    }
  }

  return (
    <section className="pageStack">
      <div className="pageTitle">
        <div>
          <span className="breadcrumb">文档库 &gt; 全部可访问</span>
          <h1>文档库</h1>
          <p>按分类、状态、标签和更新时间统一管理组织知识。</p>
        </div>
        <button className="primaryAction" onClick={onCreate}>
          <Save size={16} />
          <span>新建文档</span>
        </button>
      </div>

      <div className="toolbar">
        <label>
          <ListFilter size={16} />
          <select value={status} onChange={(event) => setStatus(event.target.value as "all" | DocumentStatus)}>
            <option value="all">全部状态</option>
            <option value="published">已发布</option>
            <option value="reviewing">审核中</option>
            <option value="draft">草稿</option>
            <option value="rejected">已驳回</option>
            <option value="archived">已归档</option>
          </select>
        </label>
        <div className="segmented">
          <button className={display === "list" ? "selected" : ""} onClick={() => setDisplay("list")} title="列表">
            <Rows3 size={16} />
          </button>
          <button className={display === "grid" ? "selected" : ""} onClick={() => setDisplay("grid")} title="网格">
            <Grid2X2 size={16} />
          </button>
        </div>
      </div>

      {message ? <div className="noticeLine">{message}</div> : null}

      <div className={display === "grid" ? "docGrid" : "docTable"}>
        {filtered.map((document) => (
          <article className="docRecord" key={document.id}>
            <div>
              <strong>{document.title}</strong>
              <p>{document.content}</p>
              <div className="tagList">
                {document.tags.map((tag) => (
                  <span key={tag}>{tag}</span>
                ))}
              </div>
            </div>
            <div className="recordMeta">
              <span>{document.author}</span>
              <span>{document.department ?? document.department_id}</span>
              <span>v{document.version}</span>
              <span className={`status ${document.status}`}>{statusText(document.status)}</span>
              <div className="recordActions">
                <button className="secondaryAction" onClick={() => onEdit(document.id)}>
                  <Edit3 size={15} />
                  <span>打开</span>
                </button>
                {document.status === "archived" ? (
                  <button className="secondaryAction" onClick={() => restoreDocument(document.id)} disabled={busyId === document.id}>
                    <ArchiveRestore size={15} />
                    <span>恢复</span>
                  </button>
                ) : (
                  <button
                    className="dangerAction"
                    onClick={() => archiveDocument(document.id)}
                    disabled={busyId === document.id || document.status === "reviewing"}
                  >
                    <Archive size={15} />
                    <span>归档</span>
                  </button>
                )}
              </div>
            </div>
          </article>
        ))}
        {!filtered.length ? <p className="emptyText">暂无匹配文档</p> : null}
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
