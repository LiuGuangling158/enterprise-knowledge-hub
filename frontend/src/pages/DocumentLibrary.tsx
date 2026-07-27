import { Edit3, Grid2X2, ListFilter, Rows3, Save } from "lucide-react";
import { useState } from "react";
import type { KnowledgeDocument } from "../types";

export function DocumentLibrary({
  documents,
  onCreate,
  onEdit
}: {
  documents: KnowledgeDocument[];
  onCreate: () => void;
  onEdit: (id: string) => void;
}) {
  const [display, setDisplay] = useState<"list" | "grid">("list");
  const [status, setStatus] = useState("all");
  const filtered = status === "all" ? documents : documents.filter((document) => document.status === status);

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
          <select value={status} onChange={(event) => setStatus(event.target.value)}>
            <option value="all">全部状态</option>
            <option value="published">已发布</option>
            <option value="reviewing">审核中</option>
            <option value="draft">草稿</option>
            <option value="rejected">已驳回</option>
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
              <button className="secondaryAction" onClick={() => onEdit(document.id)}>
                <Edit3 size={15} />
                <span>打开</span>
              </button>
            </div>
          </article>
        ))}
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
