import { Bot, CheckCircle2, Database, FileText, GitBranch, Route, Search, Send, ShieldCheck, Wrench, X } from "lucide-react";
import { FormEvent, useEffect, useState } from "react";
import { api } from "../services/api";
import type { ConversationMessage } from "../types";

interface Citation {
  document_id?: string;
  title: string;
  citation: string;
  section?: string;
  snippet?: string;
  version?: number;
  score?: number;
  author?: string;
  department?: string;
}

interface Message {
  role: "user" | "assistant";
  content: string;
  citations?: Citation[];
}

interface AgentTraceEvent extends Record<string, unknown> {
  event: string;
  agent?: string;
  agent_name?: string;
  objective?: string;
  output?: string;
  tool?: string;
  intent?: string;
  reason?: string;
  strategy?: string;
  confidence?: string | number;
  hit_count?: number;
  citation_count?: number;
  rewritten_query?: string;
  hits?: Array<Record<string, unknown>>;
  steps?: Array<Record<string, unknown>>;
  support_points?: string[];
  answer_preview?: string;
}

const welcomeMessage: Message = {
  role: "assistant",
  content: "可以直接询问制度、流程、项目背景或跨文档对比问题。回答会尽量附上来源。"
};

function getSessionId(userId: string) {
  const storageKey = `knowledge_platform_session_${userId}`;
  const existing = localStorage.getItem(storageKey);
  if (existing) return existing;

  const randomPart =
    typeof crypto !== "undefined" && "randomUUID" in crypto
      ? crypto.randomUUID().slice(0, 12)
      : Math.random().toString(36).slice(2, 14);
  const next = `qa-${Date.now().toString(36)}-${randomPart}`;
  localStorage.setItem(storageKey, next);
  return next;
}

function citationsFromMeta(meta: Record<string, unknown>): Citation[] | undefined {
  const citations = meta.citations;
  if (!Array.isArray(citations)) return undefined;

  return citations
    .map((item) => {
      if (!item || typeof item !== "object") return null;
      const citation = item as Record<string, unknown>;
      if (typeof citation.title !== "string" || typeof citation.citation !== "string") return null;
      return {
        document_id: typeof citation.document_id === "string" ? citation.document_id : undefined,
        title: citation.title,
        citation: citation.citation,
        section: typeof citation.section === "string" ? citation.section : undefined,
        snippet: typeof citation.snippet === "string" ? citation.snippet : undefined,
        version: typeof citation.version === "number" ? citation.version : undefined,
        score: typeof citation.score === "number" ? citation.score : undefined,
        author: typeof citation.author === "string" ? citation.author : undefined,
        department: typeof citation.department === "string" ? citation.department : undefined
      };
    })
    .filter(Boolean) as Citation[];
}

function messageFromHistory(message: ConversationMessage): Message {
  return {
    role: message.role,
    content: message.content,
    citations: message.role === "assistant" ? citationsFromMeta(message.meta) : undefined
  };
}

function traceFromHistory(messages: ConversationMessage[]): AgentTraceEvent[] {
  const latestAssistant = [...messages].reverse().find((message) => message.role === "assistant");
  const agentTrace = latestAssistant?.meta.agent_trace;
  if (!Array.isArray(agentTrace)) return [];
  return agentTrace
    .filter((item): item is AgentTraceEvent => Boolean(item) && typeof item === "object" && "event" in item)
    .map((item) => item as AgentTraceEvent);
}

function iconForTrace(item: AgentTraceEvent) {
  if (item.event === "tool_call" || item.event === "tool_result") return Wrench;
  if (item.event === "agent_plan") return GitBranch;
  if (item.event === "guardrail_result") return ShieldCheck;
  if (item.event === "conversation_saved" || item.agent === "memory") return Database;
  if (item.agent === "router") return Route;
  if (item.agent === "retrieval") return Search;
  if (item.event === "agent_complete") return CheckCircle2;
  return Bot;
}

function traceTitle(item: AgentTraceEvent) {
  if (item.event === "agent_plan") return "执行计划";
  if (item.event === "tool_call") return `${item.agent_name || item.agent || "Agent"} 调用工具`;
  if (item.event === "tool_result") return `${item.tool || "工具"} 返回结果`;
  if (item.event === "guardrail_result") return "证据校验";
  if (item.event === "conversation_saved") return "记忆保存";
  if (item.event === "agent_complete") return "任务完成";
  if (item.event === "agent_start") return `${item.agent_name || item.agent || "Agent"} 启动`;
  if (item.event === "agent_result") return `${item.agent_name || item.agent || "Agent"} 完成`;
  return item.event;
}

function traceDescription(item: AgentTraceEvent) {
  if (item.output) return item.output;
  if (item.objective) return String(item.objective);
  if (item.event === "agent_plan" && Array.isArray(item.steps)) return `计划 ${item.steps.length} 个执行步骤`;
  if (item.event === "tool_call") return `工具：${item.tool || "unknown"}`;
  if (item.event === "tool_result") return `命中 ${item.hit_count ?? 0} 条证据`;
  if (item.event === "guardrail_result") return `置信度：${item.confidence || "unknown"}，引用 ${item.citation_count ?? 0} 个`;
  if (item.event === "agent_complete") return `置信度：${item.confidence || "unknown"}`;
  if (item.intent) return `意图：${item.intent}`;
  if (item.rewritten_query) return `改写查询：${item.rewritten_query}`;
  return "";
}

export function KnowledgePanel({ open, onClose, userId }: { open: boolean; onClose: () => void; userId: string }) {
  const [sessionId, setSessionId] = useState(() => getSessionId(userId));
  const [messages, setMessages] = useState<Message[]>([welcomeMessage]);
  const [input, setInput] = useState("");
  const [running, setRunning] = useState(false);
  const [trace, setTrace] = useState<AgentTraceEvent[]>([]);

  useEffect(() => {
    const nextSessionId = getSessionId(userId);
    setSessionId(nextSessionId);
    setMessages([welcomeMessage]);
    setTrace([]);
  }, [userId]);

  useEffect(() => {
    if (!open || !sessionId) return;

    let cancelled = false;
    api
      .conversation(sessionId)
      .then((conversation) => {
        if (cancelled) return;
        const history = conversation.messages.map(messageFromHistory);
        setMessages(history.length ? history : [welcomeMessage]);
        setTrace(traceFromHistory(conversation.messages));
      })
      .catch(() => {
        if (!cancelled) setMessages((current) => (current.length ? current : [welcomeMessage]));
      });

    return () => {
      cancelled = true;
    };
  }, [open, sessionId]);

  async function submit(event: FormEvent) {
    event.preventDefault();
    const question = input.trim();
    if (!question || running) return;

    setMessages((current) => [...current, { role: "user", content: question }, { role: "assistant", content: "" }]);
    setInput("");
    setRunning(true);
    setTrace([]);

    try {
      await api.ask(
        sessionId,
        question,
        (delta) => {
          setMessages((current) => {
            const next = [...current];
            const last = next[next.length - 1];
            next[next.length - 1] = { ...last, content: last.content + delta };
            return next;
          });
        },
        (meta) => {
          const traceEvent = meta as AgentTraceEvent;
          setTrace((current) => [...current, traceEvent]);
          if (traceEvent.event === "agent_complete" && Array.isArray(traceEvent.citations)) {
            setMessages((current) => {
              const next = [...current];
              const last = next[next.length - 1];
              next[next.length - 1] = { ...last, citations: traceEvent.citations as Citation[] };
              return next;
            });
          }
        }
      );
    } catch {
      setMessages((current) => {
        const next = [...current];
        next[next.length - 1] = {
          role: "assistant",
          content: "当前无法完成问答请求，请确认后端服务和登录状态正常。"
        };
        return next;
      });
    } finally {
      setRunning(false);
    }
  }

  return (
    <aside className={open ? "knowledgePanel open" : "knowledgePanel"} aria-hidden={!open}>
      <div className="panelHeader">
        <div>
          <strong>知识问答</strong>
          <span>引用可追踪，历史会自动保存</span>
        </div>
        <button className="iconButton" onClick={onClose} title="关闭">
          <X size={18} />
        </button>
      </div>
      <div className="messageList">
        {messages.map((message, index) => (
          <div className={`message ${message.role}`} key={`${message.role}-${index}`}>
            <p>{message.content || "正在整理回答..."}</p>
            {message.citations?.length ? (
              <div className="citations">
                {message.citations.map((citation) => (
                  <button key={citation.citation} title={citation.snippet || citation.citation}>
                    <FileText size={14} />
                    <span>
                      {citation.title}
                      {citation.version ? <small>v{citation.version} · {citation.section || "正文"}</small> : null}
                    </span>
                  </button>
                ))}
              </div>
            ) : null}
          </div>
        ))}
        {trace.length ? (
          <section className="agentTracePanel">
            <div className="traceHeader">
              <Bot size={16} />
              <div>
                <strong>Agent 执行链路</strong>
                <span>{trace.find((item) => item.event === "agent_complete")?.confidence ? "已完成" : "运行中"}</span>
              </div>
            </div>
            <div className="agentTraceSteps">
              {trace.map((item, index) => {
                const Icon = iconForTrace(item);
                return (
                  <article className="agentTraceItem" key={`${item.event}-${index}`}>
                    <Icon size={15} />
                    <div>
                      <strong>{traceTitle(item)}</strong>
                      {traceDescription(item) ? <p>{traceDescription(item)}</p> : null}
                      {item.event === "agent_plan" && Array.isArray(item.steps) && item.steps.length ? (
                        <div className="tracePlanList">
                          {item.steps.map((step, stepIndex) => (
                            <span key={`${String(step.agent)}-${stepIndex}`}>
                              {String(step.agent_name || step.agent)}：{String(step.objective || step.output || "等待执行")}
                            </span>
                          ))}
                        </div>
                      ) : null}
                      {item.event === "tool_result" && Array.isArray(item.hits) && item.hits.length ? (
                        <div className="traceHitList">
                          {item.hits.slice(0, 3).map((hit) => (
                            <span key={String(hit.citation)}>{String(hit.title)} · v{String(hit.version)} · {String(hit.score)}</span>
                          ))}
                        </div>
                      ) : null}
                      {Array.isArray(item.support_points) && item.support_points.length ? (
                        <div className="traceHitList">
                          {item.support_points.slice(0, 3).map((point) => (
                            <span key={point}>{point}</span>
                          ))}
                        </div>
                      ) : null}
                      {item.answer_preview ? <p className="traceAnswerPreview">{item.answer_preview}</p> : null}
                    </div>
                  </article>
                );
              })}
            </div>
            <details className="trace">
              <summary>原始事件</summary>
              {trace.map((item, index) => (
                <code key={index}>{JSON.stringify(item)}</code>
              ))}
            </details>
          </section>
        ) : null}
      </div>
      <form className="questionForm" onSubmit={submit}>
        <input value={input} onChange={(event) => setInput(event.target.value)} placeholder="输入问题" />
        <button type="submit" disabled={running} title="发送">
          <Send size={18} />
        </button>
      </form>
    </aside>
  );
}
