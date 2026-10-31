/** Own NDJSON framing and reader cleanup at the HTTP boundary. */
import { isRecord } from '@/lib/json';

export type SessionStreamEvent = Record<string, unknown>;

function parseEvent(line: string): SessionStreamEvent {
  let value: unknown;
  try {
    value = JSON.parse(line);
  } catch {
    throw new Error('Session stream contains an invalid event');
  }
  // Older servers may retain the custom-channel envelope.
  if (Array.isArray(value) && value[0] === 'custom') value = value[1];
  if (!isRecord(value)) throw new Error('Session stream contains an invalid event');
  return value;
}

export async function* readSessionEvents(response: Response): AsyncGenerator<SessionStreamEvent> {
  if (!response.body) throw new Error('Session stream has no response body');
  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = '';
  try {
    while (true) {
      const { done, value } = await reader.read();
      buffer += decoder.decode(value, { stream: !done });
      const lines = buffer.split('\n');
      buffer = lines.pop() ?? '';
      for (const line of lines) if (line.trim()) yield parseEvent(line);
      if (done) break;
    }
    if (buffer.trim()) yield parseEvent(buffer);
  } finally {
    try { await reader.cancel().catch(() => undefined); } finally { reader.releaseLock(); }
  }
}
