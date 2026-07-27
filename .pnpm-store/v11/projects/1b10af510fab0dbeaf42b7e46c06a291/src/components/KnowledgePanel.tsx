import { FileText, Send, X } from "lucide-react";
import { FormEvent, useEffect, useState } from "react";
import { api } from "../services/api";
import type { ConversationMessage } from "../types";

interface Citation {
  title: string;
  citation: string;
}

interface Message {
  role: "user" | "assistant";
  content: string;
  citations?: Citation[];
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
      return { title: citation.title, citation: citation.citation };
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

export function KnowledgePanel({ open, onClose, userId }: { open: boolean; onClose: () => void; userId: string }) {
  const [sessionId, setSessionId] = useState(() => getSessionId(userId));
  const [messages, setMessages] = useState<Message[]>([welcomeMessage]);
  const [input, setInput] = useState("");
  const [running, setRunning] = useState(false);
  const [trace, setTrace] = useState<Array<Record<string, unknown>>>([]);

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
          setTrace((current) => [...current, meta]);
          if (meta.event === "agent_complete" && Array.isArray(meta.citations)) {
            setMessages((current) => {
              const next = [...current];
              const last = next[next.length - 1];
              next[next.length - 1] = { ...last, citations: meta.citations as Citation[] };
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
                  <button key={citation.citation} title={citation.citation}>
                    <FileText size={14} />
                    <span>{citation.title}</span>
                  </button>
                ))}
              </div>
            ) : null}
          </div>
        ))}
        {trace.length ? (
          <details className="trace">
            <summary>查看执行详情</summary>
            {trace.map((item, index) => (
              <code key={index}>{JSON.stringify(item)}</code>
            ))}
          </details>
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
