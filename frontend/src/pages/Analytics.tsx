import type { MetricSnapshot } from "../types";

export function Analytics({ metrics }: { metrics: MetricSnapshot }) {
  const maxReads = Math.max(...metrics.trend.map((item) => item.reads), 1);

  return (
    <section className="pageStack">
      <div className="pageTitle">
        <div>
          <h1>数据看板</h1>
          <p>观察文档增长、阅读活跃度和高价值内容。</p>
        </div>
      </div>

      <section className="panelBlock">
        <div className="sectionHeader">
          <h2>周维度趋势</h2>
          <span>新增量与阅读量</span>
        </div>
        <div className="trendChart">
          {metrics.trend.map((item) => (
            <div className="trendColumn" key={item.day}>
              <div className="bar reads" style={{ height: `${Math.max((item.reads / maxReads) * 160, 24)}px` }} />
              <div className="bar docs" style={{ height: `${Math.max(item.documents * 12, 24)}px` }} />
              <span>{item.day}</span>
            </div>
          ))}
        </div>
      </section>

      <section className="panelBlock">
        <div className="sectionHeader">
          <h2>Top 文档</h2>
          <span>按阅读量排序</span>
        </div>
        <div className="documentRows">
          {metrics.top_documents.map((document) => (
            <article className="rowItem" key={document.id}>
              <div>
                <strong>{document.title}</strong>
                <span>{document.author}</span>
              </div>
              <strong>{document.reads}</strong>
            </article>
          ))}
        </div>
      </section>
    </section>
  );
}
