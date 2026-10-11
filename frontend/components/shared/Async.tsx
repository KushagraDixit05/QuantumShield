"use client";
import type { ReactNode } from "react";
import type { ApiState } from "@/lib/api/useApi";
import { EmptyState } from "./EmptyState";

/** Renders loading / error EmptyState, otherwise the children with the data. */
export function Async<T>({ state, what, children }: { state: ApiState<T>; what: string; children: (data: T) => ReactNode }) {
  if (state.loading) return <p className="muted" role="status">Loading {what}...</p>;
  if (state.error || !state.data) return <EmptyState title={`${what} unavailable`} error={state.error ?? "empty response"} />;
  return <>{children(state.data)}</>;
}
