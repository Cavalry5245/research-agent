import { Navigate, createBrowserRouter } from "react-router-dom";
import { AppLayout } from "../components/layout/AppLayout";
import { AgentPage } from "../pages/agent/AgentPage";
import { ComparePage } from "../pages/compare/ComparePage";
import { DashboardPage } from "../pages/dashboard/DashboardPage";
import { KnowledgeBasePage } from "../pages/knowledge-base/KnowledgeBasePage";
import { MonitorPage } from "../pages/monitor/MonitorPage";
import { NotesPage } from "../pages/notes/NotesPage";
import { PaperDetailPage } from "../pages/paper-detail/PaperDetailPage";
import { PapersPage } from "../pages/papers/PapersPage";
import { QaPage } from "../pages/qa/QaPage";
import { SettingsPage } from "../pages/settings/SettingsPage";
import { WorkflowPage } from "../pages/workflow/WorkflowPage";
import { NewRunPage } from "../pages/workflow/NewRunPage";

export const router = createBrowserRouter([
  {
    path: "/",
    element: <AppLayout />,
    children: [
      { index: true, element: <Navigate to="/dashboard" replace /> },
      { path: "dashboard", element: <DashboardPage /> },
      { path: "workflow", element: <WorkflowPage /> },
      { path: "workflow/new", element: <NewRunPage /> },
      { path: "papers", element: <PapersPage /> },
      { path: "papers/:paperId", element: <PaperDetailPage /> },
      { path: "notes", element: <NotesPage /> },
      { path: "qa", element: <QaPage /> },
      { path: "compare", element: <ComparePage /> },
      { path: "knowledge-base", element: <KnowledgeBasePage /> },
      { path: "agent", element: <AgentPage /> },
      { path: "monitor", element: <MonitorPage /> },
      { path: "settings", element: <SettingsPage /> }
    ]
  }
]);
