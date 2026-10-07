export interface DialogueMessage {
  role: "player" | "npc";
  message: string;
}

export function responseMessage(payload: unknown): string | undefined {
  if (typeof payload !== "object" || payload === null) return;
  if ("success" in payload && payload.success === true && "message" in payload &&
      typeof payload.message === "string" && payload.message.trim()) return payload.message;
}

export function sessionMessages(payload: unknown): DialogueMessage[] | undefined {
  if (typeof payload !== "object" || payload === null || !("messages" in payload) ||
      !Array.isArray(payload.messages)) return;
  const messages: DialogueMessage[] = [];
  for (const entry of payload.messages) {
    if (typeof entry !== "object" || entry === null || !("role" in entry) ||
        !("message" in entry) || entry.role !== "player" && entry.role !== "npc" ||
        typeof entry.message !== "string" || !entry.message.trim()) return;
    messages.push({ role: entry.role, message: entry.message });
  }
  return messages;
}
