import { ArrowRight, BookOpen, CheckCircle2, Clock3, Users } from "lucide-react";
import type { ApprovalItem, KnowledgeDocument, MetricSnapshot } from "../types";

interface DashboardProps {
  documents: KnowledgeDocument[];
  approvals: ApprovalItem[];
  metrics: MetricSnapshot;
  onOpenKnowledge: () => void;
}

export function Dashboard({ documents, approvals, metrics, onOpenKnowledge }: DashboardProps) {
  const pending = approvals.filter((item) => item.status === "pending");

  return (
    <section className="pageStack">
      <div className="pageTitle">
        <div>
          <h1>控制台</h1>
          <p>集中查看最近文档、审批任务和组织知识使用情况。</p>
        </div>
        <button className="primaryAction" onClick={onOpenKnowledge}>
          <span>问知识库</span>
          <ArrowRight size={18} />
        </button>
      </div>

      <div className="metricGrid">
        <Metric label="文档总数" value={metrics.document_total} Icon={BookOpen} />
        <Metric label="本周新增" value={metrics.weekly_new} Icon={Clock3} />
        <Metric label="活跃用户" value={metrics.active_users} Icon={Users} />
        <Metric label="待审批" value={metrics.pending_approvals} Icon={CheckCircle2} />
      </div>

      <div className="twoColumn">
        <section className="panelBlock">
          <div className="sectionHeader">
            <h2>最近浏览文档</h2>
            <span>{documents.length} 份可访问</span>
          </div>
          <div className="documentRows">
            {documents.slice(0, 5).map((document) => (
              <article className="rowItem" key={document.id}>
                <div>
                  <strong>{document.title}</strong>
                  <span>{document.author} 更新于 {formatDate(document.updated_at)}</span>
                </div>
                <span className={`status ${document.status}`}>v{document.version}</span>
              </article>
            ))}
          </div>
        </section>

        <section className="panelBlock">
          <div className="sectionHeader">
            <h2>待审批文档</h2>
            <span>{pending.length} 项</span>
          </div>
          <div className="documentRows">
            {pending.map((item) => (
              <article className="rowItem" key={item.id}>
                <div>
                  <strong>{item.title}</strong>
                  <span>{item.submitter} 提交于 {formatDate(item.submitted_at)}</span>
                </div>
                <span className="status pending">待处理</span>
              </article>
            ))}
            {!pending.length ? <p className="emptyText">暂无待审批文档</p> : null}
          </div>
        </section>
      </div>
    </section>
  );
}

function Metric({ label, value, Icon }: { label: string; value: number; Icon: typeof BookOpen }) {
  return (
    <article className="metricItem">
      <Icon size={20} />
      <span>{label}</span>
      <strong>{value}</strong>
    </article>
  );
}

function formatDate(value: string) {
  return new Intl.DateTimeFormat("zh-CN", { month: "2-digit", day: "2-digit", hour: "2-digit", minute: "2-digit" }).format(new Date(value));
}
