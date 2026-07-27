import { Component, type ErrorInfo, type ReactNode } from "react";
import { RefreshCw, Trash2 } from "lucide-react";

interface AppErrorBoundaryProps {
  children: ReactNode;
}

interface AppErrorBoundaryState {
  error: Error | null;
}

export class AppErrorBoundary extends Component<AppErrorBoundaryProps, AppErrorBoundaryState> {
  state: AppErrorBoundaryState = {
    error: null
  };

  static getDerivedStateFromError(error: Error): AppErrorBoundaryState {
    return { error };
  }

  componentDidCatch(error: Error, info: ErrorInfo) {
    console.error("Application render failed", error, info);
  }

  reload() {
    window.location.reload();
  }

  resetLocalState() {
    localStorage.removeItem("knowledge_platform_token");
    Object.keys(localStorage)
      .filter((key) => key.startsWith("knowledge_platform_session_"))
      .forEach((key) => localStorage.removeItem(key));
    window.location.reload();
  }

  render() {
    if (!this.state.error) return this.props.children;

    return (
      <main className="errorShell">
        <section className="errorPanel">
          <div>
            <span className="breadcrumb">前端运行异常</span>
            <h1>页面加载失败</h1>
            <p>应用遇到运行时错误，已阻止白屏。可以先刷新页面；如果仍失败，清理本地登录状态后重新登录。</p>
          </div>
          <pre>{this.state.error.message}</pre>
          <div className="buttonGroup">
            <button className="secondaryAction" onClick={() => this.reload()}>
              <RefreshCw size={16} />
              <span>刷新页面</span>
            </button>
            <button className="dangerAction" onClick={() => this.resetLocalState()}>
              <Trash2 size={16} />
              <span>清理本地状态</span>
            </button>
          </div>
        </section>
      </main>
    );
  }
}
