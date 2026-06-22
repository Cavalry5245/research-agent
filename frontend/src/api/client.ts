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

export async function apiGet<T>(path: string): Promise<T> {
  const response = await fetch(path, {
    headers: { Accept: "application/json" }
  });

  return parseJsonResponse<T>(response);
}

export async function apiJson<T>(path: string, options: JsonRequestOptions = {}): Promise<T> {
  const response = await fetch(path, {
    method: options.method ?? "POST",
    headers: {
      Accept: "application/json",
      "Content-Type": "application/json"
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
    headers: { Accept: "application/json" },
    body
  });

  return parseJsonResponse<T>(response);
}
