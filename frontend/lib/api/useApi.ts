"use client";
import { useEffect, useState } from "react";

export interface ApiState<T> {
  data: T | null;
  error: string | null;
  loading: boolean;
}

/** Fetch once on mount (and whenever `deps` change). Never invents data: on failure `data` is null. */
export function useApi<T>(fetcher: () => Promise<T>, deps: readonly unknown[] = []): ApiState<T> {
  const [state, setState] = useState<ApiState<T>>({ data: null, error: null, loading: true });
  useEffect(() => {
    let live = true;
    fetcher().then(
      (data) => live && setState({ data, error: null, loading: false }),
      (e: unknown) => live && setState({ data: null, error: e instanceof Error ? e.message : String(e), loading: false }),
    );
    return () => {
      live = false;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, deps);
  return state;
}
