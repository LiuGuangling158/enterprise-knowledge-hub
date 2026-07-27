import { Check, X } from "lucide-react";
import { useState } from "react";
import type { ApprovalItem } from "../types";

export function ApprovalCenter({
  approvals,
  onReview
}: {
  approvals: ApprovalItem[];
  onReview: (approvalId: string, action: "approve" | "reject", reason?: string) => Promise<void>;
}) {
  const [reasons, setReasons] = useState<Record<string, string>>({});
  const [runningId, setRunningId] = useState<string | null>(null);
  const [message, setMessage] = useState("");
  const pending = approvals.filter((item) => item.status === "pending");
  const finished = approvals.filter((item) => item.status !== "pending");

  async function review(item: ApprovalItem, action: "approve" | "reject") {
    const reason = reasons[item.id]?.trim();
    if (action === "reject" && !reason) {
      setMessage("驳回时需要填写原因");
      return;
    }
    setRunningId(item.id);
    setMessage("");
    try {
      await onReview(item.id, action, reason);
      setMessage(action === "approve" ? "已通过审批" : "已驳回审批");
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "审批操作失败");
    } finally {
      setRunningId(null);
    }
  }

  return (
    <section className="pageStack">
      <div className="pageTitle">
        <div>
          <h1>发布审批</h1>
          <p>检查文档版本变更、审批记录和驳回原因。</p>
        </div>
      </div>

      {message ? <div className="noticeLine">{message}</div> : null}

      <section className="panelBlock">
        <div className="sectionHeader">
          <h2>待审批</h2>
          <span>{pending.length} 项</span>
        </div>
        <div className="approvalList">
          {pending.map((item) => (
            <article className="approvalItem" key={item.id}>
              <div>
                <strong>{item.title}</strong>
                <span>{item.submitter} 提交于 {formatDate(item.submitted_at)}</span>
                <p>{item.summary}</p>
                <textarea
                  value={reasons[item.id] ?? ""}
                  onChange={(event) => setReasons((current) => ({ ...current, [item.id]: event.target.value }))}
                  placeholder="审批意见或驳回原因"
                />
              </div>
              <div className="approvalActions">
                <button className="primaryAction" disabled={runningId === item.id} onClick={() => review(item, "approve")}>
                  <Check size={16} />
                  <span>通过</span>
                </button>
                <button className="dangerAction" disabled={runningId === item.id} onClick={() => review(item, "reject")}>
                  <X size={16} />
                  <span>驳回</span>
                </button>
              </div>
            </article>
          ))}
          {!pending.length ? <p className="emptyText">暂无待审批文档</p> : null}
        </div>
      </section>

      <section className="panelBlock">
        <div className="sectionHeader">
          <h2>已审批</h2>
          <span>{finished.length} 项</span>
        </div>
        <div className="documentRows">
          {finished.map((item) => (
            <article className="rowItem" key={item.id}>
              <div>
                <strong>{item.title}</strong>
                <span>审批人 {item.reviewer ?? "未记录"}</span>
                {item.reason ? <span>意见：{item.reason}</span> : null}
              </div>
              <span className={`status ${item.status}`}>{item.status === "approved" ? "已通过" : "已驳回"}</span>
            </article>
          ))}
        </div>
      </section>
    </section>
  );
}

function formatDate(value: string) {
  return new Intl.DateTimeFormat("zh-CN", { month: "2-digit", day: "2-digit", hour: "2-digit", minute: "2-digit" }).format(new Date(value));
}
