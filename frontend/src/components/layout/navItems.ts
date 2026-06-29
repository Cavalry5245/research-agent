import {
  Activity,
  Bot,
  Brain,
  Files,
  GitCompare,
  Home,
  Library,
  MessageSquare,
  NotebookText,
  Settings,
  Workflow
} from "lucide-react";
import type { ComponentType } from "react";

export interface NavItem {
  label: string;
  path: string;
  icon: ComponentType<{ className?: string }>;
}

export const navItems: NavItem[] = [
  { label: "Dashboard", path: "/dashboard", icon: Home },
  { label: "Workflow", path: "/workflow", icon: Workflow },
  { label: "Papers", path: "/papers", icon: Files },
  { label: "Notes", path: "/notes", icon: NotebookText },
  { label: "QA", path: "/qa", icon: MessageSquare },
  { label: "Compare", path: "/compare", icon: GitCompare },
  { label: "Research Sets", path: "/knowledge-base", icon: Library },
  { label: "Agent", path: "/agent", icon: Bot },
  { label: "Monitor", path: "/monitor", icon: Activity },
  { label: "Settings", path: "/settings", icon: Settings }
];

export const appIcon = Brain;
