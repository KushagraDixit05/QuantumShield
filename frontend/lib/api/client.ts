import type {
  CertificateVerifyRequest,
  CertificateVerifyResponse,
  ConsensusView,
  HealthResponse,
  LimitationsResponse,
  OverheadsResponse,
  ReceiptsResponse,
  ResultName,
  ResultsResponse,
  RunCreated,
  RunEvent,
  RunRequest,
  ScenariosResponse,
  ZkRoundsResponse,
} from "./types";

export const API_URL = (process.env.NEXT_PUBLIC_API_URL ?? "http://127.0.0.1:8000").replace(/\/$/, "");

export class ApiError extends Error {
  constructor(
    message: string,
    public status: number | null,
  ) {
    super(message);
    this.name = "ApiError";
  }
}

function detailText(detail: unknown): string {
  if (typeof detail === "string") return detail;
  if (Array.isArray(detail)) {
    return detail
      .map((d) => (d && typeof d === "object" && "msg" in d ? String((d as { msg: unknown }).msg) : JSON.stringify(d)))
      .join("; ");
  }
  return detail === undefined ? "" : JSON.stringify(detail);
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  let res: Response;
  try {
    res = await fetch(`${API_URL}${path}`, { cache: "no-store", ...init });
  } catch {
    throw new ApiError(`Cannot reach backend at ${API_URL} (${path})`, null);
  }
  if (!res.ok) {
    let detail = "";
    try {
      detail = detailText(((await res.json()) as { detail?: unknown }).detail);
    } catch {
      /* body not JSON */
    }
    throw new ApiError(`${path}: HTTP ${res.status}${detail ? ` - ${detail}` : ""}`, res.status);
  }
  return (await res.json()) as T;
}

const post = <T>(path: string, body: unknown) =>
  request<T>(path, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) });

export const getHealth = () => request<HealthResponse>("/api/health");
export const getScenarios = () => request<ScenariosResponse>("/api/scenarios");
export const createRun = (body: RunRequest) => post<RunCreated>("/api/runs", body);
export const getResults = (name: ResultName) => request<ResultsResponse>(`/api/results/${name}`);
export const getReceipts = () => request<ReceiptsResponse>("/api/receipts");
export const getZkRounds = () => request<ZkRoundsResponse>("/api/zk/rounds");
export const getConsensus = (runId: string) => request<ConsensusView>(`/api/consensus/${encodeURIComponent(runId)}`);
export const verifyCertificate = (body: CertificateVerifyRequest) =>
  post<CertificateVerifyResponse>("/api/certificates/verify", body);
export const getLimitations = () => request<LimitationsResponse>("/api/limitations");
export const getOverheads = () => request<OverheadsResponse>("/api/overheads");

/**
 * Subscribe to a run's SSE stream. Returns a close function. The stream replays from the start on
 * reconnect (contract), so the helper closes the EventSource itself after `done` / `error` rather
 * than letting the browser reconnect. `onFail` is called for transport errors (backend gone).
 */
export function streamRun(id: string, onEvent: (e: RunEvent) => void, onFail?: (message: string) => void): () => void {
  const es = new EventSource(`${API_URL}/api/runs/${encodeURIComponent(id)}/stream`);
  es.onmessage = (m: MessageEvent<string>) => {
    let ev: RunEvent;
    try {
      ev = JSON.parse(m.data) as RunEvent;
    } catch {
      onFail?.("Malformed event from backend stream");
      return;
    }
    onEvent(ev);
    if (ev.type === "done" || ev.type === "error") es.close();
  };
  es.onerror = () => {
    if (es.readyState !== EventSource.CLOSED) es.close();
    onFail?.(`Run stream for ${id} was interrupted or the backend is unreachable`);
  };
  return () => es.close();
}
