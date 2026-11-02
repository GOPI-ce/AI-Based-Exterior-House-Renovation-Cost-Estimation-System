// Anonymous per-browser identity. Projects are scoped to this id (sent as X-Workspace-Id),
// so people can save work without signing up. Clearing site data starts a new workspace.

const KEY = "facade-ai.workspace-id";
let cached: string | null = null;

export function getWorkspaceId(): string {
  if (cached) return cached;
  try {
    cached = localStorage.getItem(KEY);
    if (!cached) {
      cached = crypto.randomUUID();
      localStorage.setItem(KEY, cached);
    }
  } catch {
    // Private mode / blocked storage: keep a per-tab id so the app still works.
    cached = crypto.randomUUID();
  }
  return cached;
}
