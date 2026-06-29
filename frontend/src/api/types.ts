export type TaskStatusValue = "queued" | "running" | "completed" | "failed" | "cancelled";

export interface PaperListItem {
  paper_id: string;
  title: string;
  abstract: string;
  created_at?: string | null;
  source?: "upload" | "zotero";
  source_id?: string | null;
}

export interface PaperTitleUpdateResponse {
  paper_id: string;
  title: string;
  status: string;
}

export interface PaperListResponse {
  count: number;
  papers: PaperListItem[];
}

export interface PaperUploadResponse {
  paper_id: string;
  filename: string;
  status: string;
  storage_path: string;
}

export interface ZoteroImportCollection {
  key: string;
  name: string;
  parent_key: string | null;
  num_items: number | null;
}

export interface ZoteroImportCollectionsResponse {
  collections: ZoteroImportCollection[];
  count: number;
}

export interface ZoteroImportItem {
  key: string;
  title: string;
  creators: string[];
  year: number | null;
  doi: string | null;
  has_pdf: boolean;
  pdf_path: string | null;
  already_imported: boolean;
  existing_paper_id: string | null;
}

export interface ZoteroImportResultItem {
  item_key: string;
  title: string;
  paper_id: string | null;
  status: "imported" | "skipped" | "failed";
  reason: string | null;
}

export interface ZoteroImportItemsResponse {
  collection_key: string;
  items: ZoteroImportItem[];
  count: number;
}

export interface ZoteroImportResponse {
  imported: ZoteroImportResultItem[];
  skipped: ZoteroImportResultItem[];
  failed: ZoteroImportResultItem[];
}

export interface ParseStatusResponse {
  paper_id: string;
  status: string;
  json_path: string;
}

export interface NoteResponse {
  paper_id: string;
  note_path: string;
  content: string;
  status?: string;
}

export interface NoteStatusItem {
  paper_id: string;
  exists: boolean;
  note_path?: string | null;
  generated_at?: string | null;
}

export interface NoteStatusListResponse {
  count: number;
  notes: NoteStatusItem[];
}

export interface DeletePaperResponse {
  paper_id: string;
  status: string;
  deleted_files: string[];
  deleted_chunks: number;
}

export interface PaperIndexDetailResponse {
  paper_id: string;
  indexed: boolean;
  chunk_count: number;
  sections: string[];
}

export interface PaperIndexSummary {
  paper_id: string;
  chunk_count: number;
  sections: string[];
}

export interface LibraryIndexStatusResponse {
  total_chunks: number;
  paper_count: number;
  papers: PaperIndexSummary[];
}

export interface SourceItem {
  paper_id: string;
  title: string;
  section: string;
  chunk_id: string;
  content: string;
  score?: number | null;
  page_number?: number | null;
  citation_label?: string | null;
}

export interface QAResponse {
  question: string;
  answer: string;
  sources: SourceItem[];
}

export interface TaskStatus {
  job_id: string;
  job_type: "paper_index" | "note_generation" | "paper_comparison" | "batch_index";
  status: TaskStatusValue;
  progress: number;
  paper_id?: string | null;
  paper_ids?: string[];
  result?: Record<string, unknown> | null;
  error?: string | null;
  retry_of?: string | null;
  created_at?: string;
  started_at?: string | null;
  completed_at?: string | null;
  updated_at?: string;
}

export interface TaskListResponse {
  count: number;
  jobs: TaskStatus[];
}

export interface CompareEvidence {
  paper_id: string;
  paper_title: string;
  section: string;
  snippet: string;
}

export interface CompareAspect {
  name: string;
  summary: string;
  key_differences: string[];
  per_paper: Record<string, string>;
  evidence: CompareEvidence[];
}

export interface PaperComparisonResult {
  overview: string;
  aspects: CompareAspect[];
  markdown: string;
}

export interface CompareResponse {
  paper_ids: string[];
  status: string;
  output_path: string;
  content: string;
  comparison?: PaperComparisonResult | null;
}

export interface AgentChatMessage {
  role: string;
  content: string;
}

export interface AgentExecuteRequest {
  task: string;
  mode?: "react" | "supervisor";
  conversation_id?: string | null;
  context?: Record<string, unknown> | null;
  chat_history?: AgentChatMessage[] | null;
}

export interface AgentExecuteResponse {
  task: string;
  answer: string;
  conversation_id?: string | null;
  task_type?: string | null;
}

export interface KnowledgeBase {
  id: string;
  name: string;
  description: string;
  paper_ids: string[];
  created_at?: string | null;
  updated_at?: string | null;
  paper_count?: number | null;
  indexed_count?: number | null;
  noted_count?: number | null;
}

export interface KnowledgeBaseCreatePayload {
  kb_id?: string;
  name: string;
  description?: string;
}

export interface KnowledgeBaseListResponse {
  count: number;
  knowledge_bases: KnowledgeBase[];
}

export interface TraceItem {
  id: string;
  conversation_id?: string | null;
  agent_id: string;
  action: string;
  input_data: Record<string, unknown>;
  output_data: Record<string, unknown>;
  duration_ms?: number | null;
  created_at: number;
  metadata: Record<string, unknown>;
}

export interface TraceListResponse {
  traces: TraceItem[];
  count: number;
}

export interface TraceStatsResponse {
  total_traces: number;
  by_agent: Record<string, number>;
  by_action: Record<string, number>;
  avg_duration_ms: number;
}
