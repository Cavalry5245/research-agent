import { apiDelete, apiGet } from "./client";
import type {
  ConversationDetail,
  ConversationListResponse,
  DeleteConversationResponse
} from "./types";

export function listConversations(kind?: string, limit = 8) {
  const params = new URLSearchParams();
  params.set("limit", String(limit));
  if (kind) params.set("kind", kind);
  return apiGet<ConversationListResponse>(`/api/conversations?${params.toString()}`);
}

export function getConversation(conversationId: string) {
  return apiGet<ConversationDetail>(`/api/conversations/${conversationId}`);
}

export function deleteConversation(conversationId: string) {
  return apiDelete<DeleteConversationResponse>(`/api/conversations/${conversationId}`);
}
