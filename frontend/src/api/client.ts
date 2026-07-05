export class ApiError extends Error {
  status: number;

  constructor(message: string, status: number) {
    super(message);
    this.name = "ApiError";
    this.status = status;
  }
}

async function parseErrorMessage(response: Response) {
  let message = response.statusText || `Request failed with ${response.status}`;
  try {
    const payload = (await response.json()) as { detail?: string; message?: string };
    message = payload.detail || payload.message || message;
  } catch {
    message = response.statusText || message;
  }
  return message;
}

async function parseJsonResponse<T>(response: Response): Promise<T> {
  if (!response.ok) {
    const message = await parseErrorMessage(response);
    throw new ApiError(message, response.status);
  }

  if (response.status === 204) {
    return undefined as T;
  }

  return (await response.json()) as T;
}

interface JsonRequestOptions {
  method?: "POST" | "PUT" | "PATCH" | "DELETE";
  body?: unknown;
}

// --- BYOK (Bring Your Own Key) ------------------------------------------------
// Visitor-supplied LLM credentials. Stored in the browser's localStorage and
// attached to every API request as X-LLM-* headers. The backend's ByokMiddleware
// publishes them to LLMClient via a ContextVar for the duration of the request.
// Keys never touch server-side storage.

const LLM_OVERRIDE_STORAGE_KEY = "ra.llmOverride";

export interface LlmOverride {
  baseUrl: string;
  apiKey: string;
  model: string;
}

export function getLlmOverride(): LlmOverride | null {
  try {
    const raw = localStorage.getItem(LLM_OVERRIDE_STORAGE_KEY);
    if (!raw) return null;
    const parsed = JSON.parse(raw) as Partial<LlmOverride>;
    if (parsed && typeof parsed.apiKey === "string" && parsed.apiKey.length > 0) {
      return {
        baseUrl: typeof parsed.baseUrl === "string" ? parsed.baseUrl : "",
        apiKey: parsed.apiKey,
        model: typeof parsed.model === "string" ? parsed.model : ""
      };
    }
  } catch {
    // ignore malformed storage
  }
  return null;
}

export function setLlmOverride(override: LlmOverride | null): void {
  if (override && override.apiKey) {
    localStorage.setItem(LLM_OVERRIDE_STORAGE_KEY, JSON.stringify(override));
  } else {
    localStorage.removeItem(LLM_OVERRIDE_STORAGE_KEY);
  }
}

function llmOverrideHeaders(): Record<string, string> {
  const override = getLlmOverride();
  if (!override) return {};
  const headers: Record<string, string> = {};
  if (override.baseUrl) headers["X-LLM-Base-URL"] = override.baseUrl;
  if (override.apiKey) headers["X-LLM-API-Key"] = override.apiKey;
  if (override.model) headers["X-LLM-Model"] = override.model;
  return headers;
}

export async function apiGet<T>(path: string): Promise<T> {
  const response = await fetch(path, {
    headers: { Accept: "application/json", ...llmOverrideHeaders() }
  });

  return parseJsonResponse<T>(response);
}

export async function apiJson<T>(path: string, options: JsonRequestOptions = {}): Promise<T> {
  const response = await fetch(path, {
    method: options.method ?? "POST",
    headers: {
      Accept: "application/json",
      "Content-Type": "application/json",
      ...llmOverrideHeaders()
    },
    body: options.body === undefined ? undefined : JSON.stringify(options.body)
  });

  return parseJsonResponse<T>(response);
}

export async function apiDelete<T>(path: string): Promise<T> {
  return apiJson<T>(path, { method: "DELETE" });
}

export async function apiUpload<T>(path: string, file: File, fieldName = "file"): Promise<T> {
  const body = new FormData();
  body.append(fieldName, file);

  const response = await fetch(path, {
    method: "POST",
    headers: { Accept: "application/json", ...llmOverrideHeaders() },
    body
  });

  return parseJsonResponse<T>(response);
}
