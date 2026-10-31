import { useCallback, useEffect, useRef } from 'react';

/** One selected view owns one request; replacement and unmount cancel its predecessor. */
export function useLatestRequest() {
  const current = useRef<AbortController>();
  useEffect(() => () => current.current?.abort(), []);
  return useCallback(() => {
    current.current?.abort();
    current.current = new AbortController();
    return current.current.signal;
  }, []);
}
