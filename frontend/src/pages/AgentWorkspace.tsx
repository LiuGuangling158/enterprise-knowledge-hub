import { Bot, Database, History, MessageSquareText, Route, Search, ShieldCheck, Wrench } from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import { api } from "../services/api";
import type { AgentCapabilities, ConversationSession } from "../types";

const emptyCapabilities: AgentCapabilities = {
  agents: [],
  tools: []
};

const agentIcons: Record<string, typeof Bot> = {
  router: Route,
  retrieval: Search,
  qa: ShieldCheck,
  memory: Database
};

export function AgentWorkspace({ onOpenKnowledge }: { onOpenKnowledge: () => void }) {
  const [capabilities, setCapabilities] = useState<AgentCapabilities>(emptyCapabilities);
  const [sessions, setSessions] = useState<ConversationSession[]>([]);
  const [message, setMessage] = useState("");

  useEffect(() => {
    let cancelled = false;
    Promise.all([api.agentCapabilities(), api.conversations()])
      .then(([agentRows, conversationRows]) => {
        if (cancelled) return;
        setCapabilities(agentRows);
        setSessions(conversationRows);
      })
      .catch((reason) => {
        if (!cancelled) setMessage(reason instanceof Error ? reason.message : "Agent 工作台加载失败");
      });

    return () => {
      cancelled = true;
    };
  }, []);

  const stats = useMemo(
    () => [
      { label: "可用 Agent", value: capabilities.agents.length },
      { label: "工具能力", value: capabilities.tools.length },
      { label: "历史会话", value: sessions.length }
    ],
    [capabilities.agents.length, capabilities.tools.length, sessions.length]
  );

  return (
    <section className="pageStack">
      <div className="pageTitle">
        <div>
          <span className="breadcrumb">知识问答 &gt; Agent 编排</span>
          <h1>Agent 工作台</h1>
          <p>查看问答 Agent 队列、工具能力和最近的可追踪会话。</p>
        </div>
        <button className="primaryAction" onClick={onOpenKnowledge}>
          <MessageSquareText size={16} />
          <span>发起问答</span>
        </button>
      </div>

      {message ? <div className="noticeLine">{message}</div> : null}

      <div className="metricGrid agentMetricGrid">
        {stats.map((item) => (
          <article className="metricItem" key={item.label}>
            <span>{item.label}</span>
            <strong>{item.value}</strong>
          </article>
        ))}
      </div>

      <div className="agentWorkspaceGrid">
        <section className="agentBand">
          <div className="sectionHeader">
            <div>
              <strong>执行队列</strong>
              <span>Router、Retrieval、QA、Memory 串联完成一次回答</span>
            </div>
            <Bot size={18} />
          </div>
          <div className="agentPipeline">
            {capabilities.agents.map((agent, index) => {
              const Icon = agentIcons[agent.id] ?? Bot;
              return (
                <article className="agentNode" key={agent.id}>
                  <div className="agentNodeIcon">
                    <Icon size={18} />
                  </div>
                  <div>
                    <strong>{agent.name}</strong>
                    <span>步骤 {index + 1}</span>
                    <p>{agent.responsibility}</p>
                    {agent.tools.length ? (
                      <div className="agentToolChips">
                        {agent.tools.map((tool) => (
                          <span key={tool}>{tool}</span>
                        ))}
                      </div>
                    ) : null}
                  </div>
                </article>
              );
            })}
          </div>
        </section>

        <section className="agentBand">
          <div className="sectionHeader">
            <div>
              <strong>工具清单</strong>
              <span>Agent 可调用的后端能力</span>
            </div>
            <Wrench size={18} />
          </div>
          <div className="toolList">
            {capabilities.tools.map((tool) => (
              <article key={tool.id}>
                <strong>{tool.name}</strong>
                <span>{tool.type}</span>
              </article>
            ))}
          </div>
        </section>

        <section className="agentBand recentConversationBand">
          <div className="sectionHeader">
            <div>
              <strong>最近会话</strong>
              <span>每次问答会保存回答、引用和 Agent 轨迹</span>
            </div>
            <History size={18} />
          </div>
          <div className="conversationList">
            {sessions.slice(0, 6).map((session) => (
              <article key={session.id}>
                <strong>{session.title}</strong>
                <span>{formatDate(session.updated_at)}</span>
              </article>
            ))}
            {!sessions.length ? <p>暂无历史会话</p> : null}
          </div>
        </section>
      </div>
    </section>
  );
}

function formatDate(value: string) {
  return new Intl.DateTimeFormat("zh-CN", {
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit"
  }).format(new Date(value));
}
