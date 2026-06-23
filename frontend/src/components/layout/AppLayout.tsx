import { Menu } from "lucide-react";
import { NavLink, Outlet } from "react-router-dom";
import { useUiStore } from "../../stores/uiStore";
import { appIcon as AppIcon, navItems } from "./navItems";

export function AppLayout() {
  const sidebarCollapsed = useUiStore((state) => state.sidebarCollapsed);
  const toggleSidebar = useUiStore((state) => state.toggleSidebar);

  return (
    <div className="min-h-screen bg-surface text-ink">
      <aside
        className={`fixed inset-y-0 left-0 z-20 border-r border-line bg-panel transition-all ${
          sidebarCollapsed ? "w-16" : "w-64"
        }`}
        aria-label="Primary navigation"
      >
        <div className="flex h-14 items-center gap-3 border-b border-line px-4">
          <AppIcon className="h-5 w-5 text-accent" aria-hidden="true" />
          {!sidebarCollapsed && <span className="text-sm font-semibold">ResearchAgent</span>}
        </div>
        <nav className="space-y-1 p-2">
          {navItems.map((item) => (
            <NavLink
              key={item.path}
              to={item.path}
              className={({ isActive }) =>
                [
                  "flex h-10 items-center gap-3 rounded-md px-3 text-sm font-medium",
                  isActive ? "bg-blue-50 text-accent" : "text-muted hover:bg-surface hover:text-ink"
                ].join(" ")
              }
              title={sidebarCollapsed ? item.label : undefined}
            >
              <item.icon className="h-4 w-4 shrink-0" aria-hidden="true" />
              {!sidebarCollapsed && <span>{item.label}</span>}
            </NavLink>
          ))}
        </nav>
      </aside>

      <div className={sidebarCollapsed ? "pl-16" : "pl-64"}>
        <header className="sticky top-0 z-10 flex h-14 items-center justify-between border-b border-line bg-panel px-6">
          <button
            type="button"
            className="inline-flex h-9 w-9 items-center justify-center rounded-md border border-line text-muted hover:bg-surface hover:text-ink"
            onClick={toggleSidebar}
            aria-label="Toggle sidebar"
          >
            <Menu className="h-4 w-4" aria-hidden="true" />
          </button>
          <div className="text-sm text-muted">
            FastAPI backend:{" "}
            {import.meta.env.VITE_API_BASE_URL?.replace("http://", "") || "127.0.0.1:8888"}
          </div>
        </header>
        <main className="p-6">
          <Outlet />
        </main>
      </div>
    </div>
  );
}
