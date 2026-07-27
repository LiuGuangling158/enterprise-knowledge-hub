import { useEffect, useMemo, useState } from "react";
import { Layout } from "./components/Layout";
import { KnowledgePanel } from "./components/KnowledgePanel";
import { ApprovalCenter } from "./pages/ApprovalCenter";
import { Analytics } from "./pages/Analytics";
import { Dashboard } from "./pages/Dashboard";
import { DocumentEditor } from "./pages/DocumentEditor";
import { DocumentLibrary } from "./pages/DocumentLibrary";
import { LoginPage } from "./pages/LoginPage";
import { api } from "./services/api";
import type { ApprovalItem, KnowledgeDocument, MetricSnapshot, UserProfile, ViewKey } from "./types";

const emptyMetrics: MetricSnapshot = {
  document_total: 0,
  weekly_new: 0,
  active_users: 0,
  pending_approvals: 0,
  trend: [],
  top_documents: []
};

export default function App() {
  const [view, setView] = useState<ViewKey>("dashboard");
  const [user, setUser] = useState<UserProfile | null>(null);
  const [documents, setDocuments] = useState<KnowledgeDocument[]>([]);
  const [archivedDocuments, setArchivedDocuments] = useState<KnowledgeDocument[]>([]);
  const [approvals, setApprovals] = useState<ApprovalItem[]>([]);
  const [metrics, setMetrics] = useState<MetricSnapshot>(emptyMetrics);
  const [query, setQuery] = useState("");
  const [panelOpen, setPanelOpen] = useState(false);
  const [selectedDocumentId, setSelectedDocumentId] = useState<string | null>(null);
  const [booting, setBooting] = useState(Boolean(api.getToken()));
  const [error, setError] = useState("");

  useEffect(() => {
    if (!api.getToken()) return;
    api
      .me()
      .then((profile) => {
        setUser(profile);
        return refreshData();
      })
      .catch(() => {
        api.clearToken();
        setUser(null);
      })
      .finally(() => setBooting(false));
  }, []);

  async function refreshData() {
    const [docRows, archivedRows, approvalRows, metricSnapshot] = await Promise.all([
      api.documents(),
      api.documents("archived"),
      api.approvals(),
      api.metrics()
    ]);
    setDocuments(docRows);
    setArchivedDocuments(archivedRows);
    setApprovals(approvalRows);
    setMetrics(metricSnapshot);
  }

  async function handleLogin(email: string, password: string) {
    setError("");
    const profile = await api.login(email, password);
    setUser(profile);
    await refreshData();
  }

  async function handleRegister(payload: { name: string; email: string; password: string; department_id: string }) {
    setError("");
    const profile = await api.register(payload);
    setUser(profile);
    await refreshData();
  }

  function handleLogout() {
    api.clearToken();
    setUser(null);
    setDocuments([]);
    setArchivedDocuments([]);
    setApprovals([]);
    setMetrics(emptyMetrics);
    setView("dashboard");
  }

  const filteredDocuments = useMemo(() => {
    return documents.filter((document) => {
      const text = `${document.title} ${document.author} ${document.tags.join(" ")} ${document.content}`;
      return text.toLowerCase().includes(query.toLowerCase());
    });
  }, [documents, query]);

  const filteredArchivedDocuments = useMemo(() => {
    return archivedDocuments.filter((document) => {
      const text = `${document.title} ${document.author} ${document.tags.join(" ")} ${document.content}`;
      return text.toLowerCase().includes(query.toLowerCase());
    });
  }, [archivedDocuments, query]);

  if (booting) {
    return <div className="bootScreen">正在恢复登录状态...</div>;
  }

  if (!user) {
    return (
      <LoginPage
        error={error}
        onLogin={(email, password) => handleLogin(email, password).catch((reason) => setError(reason.message))}
        onRegister={(payload) => handleRegister(payload).catch((reason) => setError(reason.message))}
      />
    );
  }

  return (
    <Layout
      activeView={view}
      user={user}
      query={query}
      onNavigate={(nextView) => {
        setView(nextView);
        if (nextView !== "editor") setSelectedDocumentId(null);
      }}
      onQueryChange={setQuery}
      onOpenKnowledge={() => setPanelOpen(true)}
      onLogout={handleLogout}
    >
      {view === "dashboard" && (
        <Dashboard documents={filteredDocuments} approvals={approvals} metrics={metrics} onOpenKnowledge={() => setPanelOpen(true)} />
      )}
      {view === "documents" && (
        <DocumentLibrary
          documents={filteredDocuments}
          archivedDocuments={filteredArchivedDocuments}
          onCreate={() => {
            setSelectedDocumentId(null);
            setView("editor");
          }}
          onEdit={(id) => {
            setSelectedDocumentId(id);
            setView("editor");
          }}
          onArchive={(id) => api.archiveDocument(id).then(() => refreshData())}
          onRestore={(id) => api.restoreDocument(id).then(() => refreshData())}
        />
      )}
      {view === "editor" && (
        <DocumentEditor
          documentId={selectedDocumentId}
          onBack={() => setView("documents")}
          onSaved={(document) => {
            setSelectedDocumentId(document.id);
            refreshData();
          }}
          onArchived={(document) => {
            setSelectedDocumentId(document.id);
            refreshData();
          }}
          onRestored={(document) => {
            setSelectedDocumentId(document.id);
            refreshData();
          }}
          onSubmitted={() => {
            refreshData();
            setView("approvals");
          }}
        />
      )}
      {view === "approvals" && (
        <ApprovalCenter
          approvals={approvals}
          onReview={(approvalId, action, reason) =>
            api.reviewApproval(approvalId, action, reason).then(() => refreshData())
          }
        />
      )}
      {view === "qa" && (
        <Dashboard documents={filteredDocuments} approvals={approvals} metrics={metrics} onOpenKnowledge={() => setPanelOpen(true)} />
      )}
      {view === "analytics" && <Analytics metrics={metrics} />}
      {view === "admin" && (
        <DocumentLibrary
          documents={filteredDocuments}
          archivedDocuments={filteredArchivedDocuments}
          onCreate={() => {
            setSelectedDocumentId(null);
            setView("editor");
          }}
          onEdit={(id) => {
            setSelectedDocumentId(id);
            setView("editor");
          }}
          onArchive={(id) => api.archiveDocument(id).then(() => refreshData())}
          onRestore={(id) => api.restoreDocument(id).then(() => refreshData())}
        />
      )}
      <KnowledgePanel open={panelOpen} onClose={() => setPanelOpen(false)} />
    </Layout>
  );
}
