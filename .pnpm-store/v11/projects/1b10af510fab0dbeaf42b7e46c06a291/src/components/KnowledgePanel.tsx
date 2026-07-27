import { FileText, Send, X } from "lucide-react";
import { FormEvent, useState } from "react";
import { api } from "../services/api";

interface Message {
  role: "user" | "assistant";
  content: string;
  citations?: Array<{ title: string; citation: string }>;
}

export function KnowledgePanel({ open, onClose }: { open: boolean; onClose: () => void }) {
  const [messages, setMessages] = useState<Message[]>([
    {
      role: "assistant",
      content: "可以直接询问制度、流程、项目背景或跨文档对比问题。回答会尽量附上来源。"
    }
  ]);
  const [input, setInput] = useState("");
  const [running, setRunning] = useState(false);
  const [trace, setTrace] = useState<Array<Record<string, unknown>>>([]);

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
              next[next.length - 1] = { ...last, citations: meta.citations as Message["citations"] };
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
          <span>引用可追溯，过程可展开</span>
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
                  <button key={citation.citation}>
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
