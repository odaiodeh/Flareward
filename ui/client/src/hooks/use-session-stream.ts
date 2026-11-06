/**
 * Hook for managing Redis-backed session stream subscription.
 * 
 * Implements the streaming pattern:
 * 1. POST /user.session.submit  ← fire & forget (returns 202 immediately)
 * 2. GET /session.subscribe ← real-time events (NDJSON stream)
 * 
 * Features:
 * - Subscribes to Redis stream for live events + historical replay
 * - Automatically reconnects when user returns to an active session
 * - Handles stream lifecycle (heartbeat, stream_end, stream_error)
 */

import { useState, useCallback, useRef, useEffect } from 'react';
import { readSessionEvents } from '@/api/session-stream';
import { 
  getSessionStreamStatus, 
  subscribeToSessionStream, 
  submitSession,
  cancelSession,
  SubmitSessionParams,
  StreamStatusResponse 
} from '@/api/sessions';

export interface UseSessionStreamOptions {
  teamId?: string;
  onChunk: (chunkData: any) => void;
  onStreamEnd?: () => void;
  onError?: (error: string) => void;
}

export interface UseSessionStreamReturn {
  executionReference: { sessionId: string; executionId: string } | null;
  isStreaming: boolean;
  isReconnecting: boolean;
  isSubmitting: boolean;
  streamStatus: StreamStatusResponse | null;
  lastEventId: string | null;
  /** Submit session for background execution and immediately subscribe to stream */
  submitAndSubscribe: (params: SubmitSessionParams) => Promise<void>;
  /** Check if session is active and reconnect if so */
  checkAndReconnect: (sessionId: string) => Promise<boolean>;
  /** Subscribe to an existing session's stream (replays all events from beginning) */
  subscribeToStream: (sessionId: string, executionId?: string) => void;
  /** Cancel the current stream subscription (client-side only) */
  cancelStream: () => void;
  /** Cancel a session's backend execution via POST /session.cancel */
  cancelSessionExecution: (sessionId: string) => Promise<void>;
}

/**
 * Hook for managing Redis-backed session stream subscription.
 */
export function useSessionStream(options: UseSessionStreamOptions): UseSessionStreamReturn {
  const { onChunk, onStreamEnd, onError, teamId } = options;
  
  const [isStreaming, setIsStreaming] = useState(false);
  const [isReconnecting, setIsReconnecting] = useState(false);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [streamStatus, setStreamStatus] = useState<StreamStatusResponse | null>(null);
  const [lastEventId, setLastEventId] = useState<string | null>(null);
  const [executionReference, setExecutionReference] = useState<UseSessionStreamReturn['executionReference']>(null);
  
  const abortControllerRef = useRef<AbortController | null>(null);
  const subscriptionGenerationRef = useRef(0);
  
  // Store callbacks in refs to avoid dependency issues
  const onChunkRef = useRef(onChunk);
  const onStreamEndRef = useRef(onStreamEnd);
  const onErrorRef = useRef(onError);
  
  // Keep refs updated
  useEffect(() => {
    onChunkRef.current = onChunk;
    onStreamEndRef.current = onStreamEnd;
    onErrorRef.current = onError;
  }, [onChunk, onStreamEnd, onError]);
  
  /**
   * Cancel any active stream subscription.
   */
  const cancelStream = useCallback(() => {
    setExecutionReference(null);
    subscriptionGenerationRef.current += 1;
    if (abortControllerRef.current) {
      abortControllerRef.current.abort();
      abortControllerRef.current = null;
    }
    setIsStreaming(false);
    setIsSubmitting(false);
    setIsReconnecting(false);
  }, []);
  
  /**
   * Subscribe to a session's Redis stream.
   * This runs asynchronously in the background - does not block.
   * 
   * The stream replays all events from the beginning, so clients that
   * connect late (or reconnect) receive the full history.
   */
  const subscribeToStream = useCallback((sessionId: string, executionId?: string, selectedTeam = teamId): void => {
    cancelStream();
    if (executionId) setExecutionReference({ sessionId, executionId });
    const controller = new AbortController();
    abortControllerRef.current = controller;
    const ownsSubscription = () => abortControllerRef.current === controller && !controller.signal.aborted;
    setLastEventId(null);

    void (async () => {
      try {
        const response = await subscribeToSessionStream(sessionId, {
          signal: controller.signal, teamId: selectedTeam, executionId,
        });
        if (!ownsSubscription()) {
          await response.body?.cancel();
          return;
        }
        setIsStreaming(true);
        for await (const event of readSessionEvents(response)) {
          if (!ownsSubscription()) return;
          if (typeof event.cursor === 'string') setLastEventId(event.cursor);
          if (event.type === 'heartbeat') continue;
          if (event.type === 'stream_end') {
            onStreamEndRef.current?.();
            return;
          }
          if (event.type === 'stream_error') {
            onErrorRef.current?.(typeof event.error === 'string' ? event.error : 'Session stream failed');
            return;
          }
          onChunkRef.current(event);
        }
        if (ownsSubscription()) onStreamEndRef.current?.();
      } catch (error: unknown) {
        if (!ownsSubscription()) return;
        onErrorRef.current?.(error instanceof Error ? error.message : 'Session stream failed');
      } finally {
        if (abortControllerRef.current === controller) {
          abortControllerRef.current = null;
          setIsStreaming(false);
        }
      }
    })();
  }, [cancelStream, teamId]);

  /**
   * Submit a session for background execution and immediately subscribe to the stream.
   * 
   * This is the primary method for new executions:
   * 1. POST /user.session.submit (fire & forget, returns 202)
   * 2. GET /session.subscribe (real-time events)
   * 
   * @param params - Session submission parameters (sessionId, inputs, scope, executionId)
   */
  const submitAndSubscribe = useCallback(async (params: SubmitSessionParams): Promise<void> => {
    // Cancel any existing stream
    cancelStream();
    setIsSubmitting(true);
    const generation = subscriptionGenerationRef.current;
    
    try {
      // Step 1: Submit session for background execution (fire & forget)
      const selectedTeam = params.teamId ?? teamId;
      const submitted = await submitSession({ ...params, teamId: selectedTeam });
      if (subscriptionGenerationRef.current !== generation) return;
      
      // Step 2: Immediately subscribe to the stream
      // The backend starts writing to Redis, we start reading
      // Stream replays all events from the beginning automatically
      subscribeToStream(params.sessionId, submitted.executionId, selectedTeam);
    } catch (err: any) {
      if (subscriptionGenerationRef.current !== generation) return;
      console.error('Error submitting session:', err);
      onErrorRef.current?.(err.message || 'Failed to submit session');
      throw err;
    } finally {
      if (subscriptionGenerationRef.current === generation) setIsSubmitting(false);
    }
  }, [cancelStream, subscribeToStream, teamId]);
  
  /**
   * Check if a session has an active stream and reconnect if so.
   * Returns true if reconnection was initiated.
   * 
   * Note: This does NOT block on stream reading - the subscription runs
   * in the background. This allows the caller to continue without blocking.
   */
  const checkAndReconnect = useCallback(async (sessionId: string): Promise<boolean> => {
    // Cancel any existing stream subscription for the UI
    // (does not cancel backend execution - just switches which stream we're listening to)
    cancelStream();
    const generation = subscriptionGenerationRef.current;
    
    setIsReconnecting(true);
    
    try {
      const status = await getSessionStreamStatus(sessionId, teamId);
      if (subscriptionGenerationRef.current !== generation) return false;
      setStreamStatus(status);
      if (status?.execution_id) setExecutionReference({ sessionId, executionId: status.execution_id });
      
      if (status && status.is_active) {
        // Session is actively streaming - start subscription in background
        // Stream replays all events from the beginning automatically
        subscribeToStream(sessionId, status.execution_id);
        setIsReconnecting(false);
        return true;
      }
      
      return false;
    } catch (err) {
      console.error('Error checking stream status:', err);
      return false;
    } finally {
      if (subscriptionGenerationRef.current === generation) setIsReconnecting(false);
    }
  }, [cancelStream, subscribeToStream, teamId]);
  
  /**
   * Cancel a session's backend execution via POST /session.cancel.
   */
  const cancelSessionExecution = useCallback(async (sessionId: string): Promise<void> => {
    await cancelSession(sessionId, teamId);
  }, [teamId]);

  // Cleanup on unmount
  useEffect(() => {
    return () => {
      cancelStream();
    };
  }, [cancelStream, teamId]);
  
  return {
    executionReference,
    isStreaming,
    isReconnecting,
    isSubmitting,
    streamStatus,
    lastEventId,
    submitAndSubscribe,
    checkAndReconnect,
    subscribeToStream,
    cancelStream,
    cancelSessionExecution,
  };
}
