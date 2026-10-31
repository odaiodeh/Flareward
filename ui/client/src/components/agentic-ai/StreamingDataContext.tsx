// StreamingDataContext.tsx
import React, { createContext, useContext, useRef, useCallback } from 'react';
import { updateApproval, type NodeEntry, type ApprovalStatus, type ApprovalIdentity } from './chat/types';

export type { NodeEntry };

type StreamingContextType = {
  nodeListRef: React.MutableRefObject<Map<string, NodeEntry>>;
  forceUpdate: () => void;
  clearStream: () => void;
  updateApprovalStatus: (
    identity: ApprovalIdentity,
    status: ApprovalStatus,
    feedback?: string,
  ) => void;
};

export const StreamingDataContext = createContext<StreamingContextType | null>(null);

export const StreamingDataProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const nodeListRef = useRef<Map<string, NodeEntry>>(new Map());
  const [, setTick] = React.useState(0);

  const forceUpdate = () => setTick(t => t + 1);

  const clearStream = () => {
    nodeListRef.current.clear();
    forceUpdate();
  };

  const updateApprovalStatus = useCallback(
    (identity: ApprovalIdentity, status: ApprovalStatus, feedback?: string) => {
      if (updateApproval(nodeListRef.current.values(), identity, status, feedback)) forceUpdate();
    },
    [],
  );

  return (
    <StreamingDataContext.Provider
      value={{ nodeListRef, forceUpdate, clearStream, updateApprovalStatus }}
    >
      {children}
    </StreamingDataContext.Provider>
  );
};

export const useStreamingData = () => {
  const context = useContext(StreamingDataContext);
  if (!context) throw new Error('useStreamingData must be used within a StreamingDataProvider');
  return context;
};
