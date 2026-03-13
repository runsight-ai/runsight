export const POLL_INTERVALS = {
  activeRun: 1_000,
  gitStatus: 5_000,
} as const;

export const QUERY_STALE_TIMES = {
  default: 5_000,
  settings: 30_000,
  souls: 10_000,
} as const;
