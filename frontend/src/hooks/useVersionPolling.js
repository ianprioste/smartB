import { useEffect, useRef } from 'react';

export function useVersionPolling({
  enabled,
  pollKey,
  fetchVersion,
  onVersionChange,
  intervalMsActive = 7000,
  intervalMsHidden = 15000,
}) {
  const timerRef = useRef(null);
  const inFlightRef = useRef(false);
  const currentVersionRef = useRef(null);
  const mountedRef = useRef(false);

  useEffect(() => {
    currentVersionRef.current = null;
  }, [pollKey]);

  useEffect(() => {
    mountedRef.current = true;
    return () => {
      mountedRef.current = false;
    };
  }, []);

  useEffect(() => {
    if (!enabled || typeof fetchVersion !== 'function') {
      return undefined;
    }

    const runPoll = async () => {
      if (!mountedRef.current || inFlightRef.current) return;
      inFlightRef.current = true;
      try {
        try {
          const nextVersion = await fetchVersion();
          if (nextVersion === null || nextVersion === undefined) return;
          const parsedVersion = Number(nextVersion);
          if (!Number.isFinite(parsedVersion)) return;

          if (currentVersionRef.current === null) {
            currentVersionRef.current = parsedVersion;
            return;
          }

          if (parsedVersion > currentVersionRef.current) {
            currentVersionRef.current = parsedVersion;
            if (typeof onVersionChange === 'function') {
              onVersionChange(parsedVersion);
            }
          }
        } catch {
          // Keep polling on transient failures.
        }
      } finally {
        inFlightRef.current = false;
      }
    };

    const schedule = () => {
      const delay = document.visibilityState === 'visible' ? intervalMsActive : intervalMsHidden;
      timerRef.current = window.setTimeout(async () => {
        await runPoll();
        schedule();
      }, delay);
    };

    runPoll();
    schedule();

    const handleVisibility = () => {
      if (timerRef.current) {
        window.clearTimeout(timerRef.current);
      }
      schedule();
    };

    document.addEventListener('visibilitychange', handleVisibility);

    return () => {
      document.removeEventListener('visibilitychange', handleVisibility);
      if (timerRef.current) {
        window.clearTimeout(timerRef.current);
      }
      timerRef.current = null;
      inFlightRef.current = false;
    };
  }, [enabled, fetchVersion, onVersionChange, intervalMsActive, intervalMsHidden]);
}
