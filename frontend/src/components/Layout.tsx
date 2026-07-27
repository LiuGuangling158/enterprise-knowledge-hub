import { BarChart3, BookOpen, CheckSquare, LogOut, MessageSquareText, Search, Settings, ShieldCheck } from "lucide-react";
import type { PropsWithChildren } from "react";
import type { UserProfile, ViewKey } from "../types";

interface LayoutProps extends PropsWithChildren {
  activeView: ViewKey;
  user: UserProfile;
  query: string;
  onNavigate: (view: ViewKey) => void;
  onQueryChange: (query: string) => void;
  onOpenKnowledge: () => void;
  onLogout: () => void;
}

const navItems: Array<{ key: ViewKey; label: string; Icon: typeof BookOpen }> = [
  { key: "dashboard", label: "控制台", Icon: BarChart3 },
  { key: "documents", label: "文档库", Icon: BookOpen },
  { key: "approvals", label: "发布审批", Icon: CheckSquare },
  { key: "qa", label: "知识问答", Icon: MessageSquareText },
  { key: "analytics", label: "数据看板", Icon: ShieldCheck },
  { key: "admin", label: "管理后台", Icon: Settings }
];

export function Layout({ activeView, user, query, onNavigate, onQueryChange, onOpenKnowledge, onLogout, children }: LayoutProps) {
  return (
    <div className="shell">
      <aside className="sidebar">
        <div className="brand">
          <div className="brandMark">K</div>
          <div>
            <strong>知识平台</strong>
            <span>内部文档协作</span>
          </div>
        </div>
        <nav className="navList">
          {navItems.map(({ key, label, Icon }) => (
            <button
              className={activeView === key ? "navButton active" : "navButton"}
              key={key}
              onClick={() => (key === "qa" ? onOpenKnowledge() : onNavigate(key))}
              title={label}
            >
              <Icon size={18} />
              <span>{label}</span>
            </button>
          ))}
        </nav>
      </aside>
      <div className="workspace">
        <header className="topbar">
          <label className="searchBox">
            <Search size={18} />
            <input value={query} onChange={(event) => onQueryChange(event.target.value)} placeholder="搜索标题、标签、正文或作者" />
          </label>
          <div className="profile">
            <div className="profileText">
              <strong>{user.name}</strong>
              <span>{user.department} {roleText(user.role)}</span>
            </div>
            <div className="avatar">{user.name.slice(0, 1).toUpperCase()}</div>
            <button className="iconButton" onClick={onLogout} title="退出登录">
              <LogOut size={17} />
            </button>
          </div>
        </header>
        <main className="content">{children}</main>
        <button className="askButton" onClick={onOpenKnowledge} title="问知识库">
          <MessageSquareText size={22} />
        </button>
      </div>
    </div>
  );
}

function roleText(role: UserProfile["role"]) {
  return {
    admin: "管理员",
    editor: "编辑",
    member: "成员"
  }[role];
}
