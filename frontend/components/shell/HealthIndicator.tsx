"use client";
import { useEffect, useState } from "react";
import { API_URL, getHealth, type HealthResponse } from "@/lib/api";

type State = { health: HealthResponse | null; error: string | null };

export function HealthIndicator() {
  const [s, setS] = useState<State>({ health: null, error: null });
  useEffect(() => {
    let live = true;
    const tick = () =>
      getHealth().then(
        (health) => live && setS({ health, error: null }),
        (e: unknown) => live && setS({ health: null, error: e instanceof Error ? e.message : String(e) }),
      );
    tick();
    const t = setInterval(tick, 10000);
    return () => {
      live = false;
      clearInterval(t);
    };
  }, []);

  const { health, error } = s;
  const state = health ? (health.ok ? "ok" : "bad") : error ? "bad" : "";
  return (
    <span className="mono" role="status" title={error ?? `Backend ${API_URL}`}>
      <i className={`qs-dot ${state}`} />{" "}
      {health
        ? `backend ${health.ok ? "up" : "unhealthy"} | queue ${health.queue_length}${health.prover_lock_held ? " | prover lock held" : ""}`
        : error
          ? "backend unreachable"
          : "backend: checking"}
    </span>
  );
}
