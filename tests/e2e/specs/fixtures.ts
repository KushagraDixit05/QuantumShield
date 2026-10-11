// Legacy import path for the Q-era specs; the implementation lives in ../shared/.
export { test, expect, settle, API, SHOTS, SSE_ABORT } from "../shared/fixtures";
export { ROOT } from "../shared/config";
export { readCsv } from "../shared/data";
export const PAGES = ["/", "/run", "/zk", "/consensus", "/overheads", "/attacks", "/limitations"] as const;
