export interface User {
  id: number
  name: string
  created_at: string
}

export interface Voiceprint {
  id: number
  user_id: number
  name: string
  audio_path: string
  created_at: string
}

export interface DetectResult {
  best_uid: number | null
  best_name: string
  best_avg: number
  users: DetectUser[]
}

export interface DetectUser {
  user_id: number
  name: string
  avg_sim: number
  voiceprints: { id: number; sim: number }[]
}

export interface HistoryMessage {
  id: number
  role: string
  content: string
}

type JsonHeaders = { "Content-Type": "application/json" }

function post(url: string, body: unknown) {
  return fetch(url, {
    method: "POST",
    headers: { "Content-Type": "application/json" } as JsonHeaders,
    body: JSON.stringify(body),
  })
}

const BASE = "/api"

export const api = {
  // Users
  listUsers: (): Promise<User[]> =>
    fetch(`${BASE}/users`).then((r) => r.json()),

  createUser: (name: string): Promise<{ id: number; ok: boolean }> =>
    post(`${BASE}/users`, { name }).then((r) => r.json()),

  renameUser: (id: number, name: string): Promise<{ ok: boolean }> =>
    fetch(`${BASE}/users/${id}?name=${encodeURIComponent(name)}`, {
      method: "PUT",
    }).then((r) => r.json()),

  deleteUser: (id: number): Promise<{ ok: boolean }> =>
    fetch(`${BASE}/users/${id}`, { method: "DELETE" }).then((r) => r.json()),

  // Voiceprints
  listVoiceprints: (userId: number): Promise<Voiceprint[]> =>
    fetch(`${BASE}/users/${userId}/voiceprints`).then((r) => r.json()),

  addVoiceprint: (userId: number, file: Blob, filename: string) => {
    const fd = new FormData()
    fd.append("file", file, filename)
    return fetch(`${BASE}/users/${userId}/voiceprints`, {
      method: "POST",
      body: fd,
    }).then((r) => {
      if (!r.ok) return r.text().then((t) => { throw new Error(t) })
      return r.json()
    })
  },

  deleteVoiceprint: (id: number) =>
    fetch(`${BASE}/voiceprints/${id}`, { method: "DELETE" }),

  moveVoiceprint: (id: number, targetUserId: number) =>
    fetch(`${BASE}/voiceprints/${id}/move?target_user_id=${targetUserId}`, {
      method: "PUT",
    }).then((r) => r.json()),

  detect: (blob: Blob): Promise<DetectResult> => {
    const fd = new FormData()
    fd.append("file", blob, "detect.webm")
    return fetch(`${BASE}/voiceprints/detect`, { method: "POST", body: fd }).then(
      (r) => r.json()
    )
  },

  // Chat history
  getHistory: (userId: number): Promise<HistoryMessage[]> =>
    fetch(`${BASE}/users/${userId}/history`).then((r) => r.json()),

  updateMessage: (msgId: number, content: string) =>
    fetch(`${BASE}/history/${msgId}`, {
      method: "PUT",
      headers: { "Content-Type": "application/json" } as JsonHeaders,
      body: JSON.stringify({ content }),
    }),

  deleteMessage: (msgId: number) =>
    fetch(`${BASE}/history/${msgId}`, { method: "DELETE" }),

  clearHistory: (userId: number) =>
    fetch(`${BASE}/users/${userId}/history`, { method: "DELETE" }),

  // Direct chat (bypass wakeword/STT)
  chat: (text: string, userId: number, speaker: string): Promise<{ reply: string }> =>
    post(`${BASE}/chat`, { text, user_id: userId, speaker }).then((r) => r.json()),
}
