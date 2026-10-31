import React, { createContext, useCallback, useContext, useEffect, useRef, useState, ReactNode } from 'react';
import {
  ShareInvite, listShares, createShare, acceptShare, declineShare, CreateShareRequest,
} from '@/api/shares';
import { useLatestRequest } from '@/hooks/use-latest-request';
import { useAuth } from './AuthContext';
import { useView } from './ViewContext';

interface NotificationContextType {
  receivedNotifications: ShareInvite[];
  sentNotifications: ShareInvite[];
  isLoading: boolean;
  error: string | null;
  pendingNotificationsCount: number;
  hasUnreadNotifications: boolean;
  refreshNotifications: () => Promise<void>;
  sendNotification: (request: CreateShareRequest) => Promise<void>;
  acceptNotification: (shareId: string) => Promise<void>;
  declineNotification: (shareId: string) => Promise<void>;
  clearError: () => void;
}

const NotificationContext = createContext<NotificationContextType | undefined>(undefined);

export const NotificationProvider: React.FC<{ children: ReactNode }> = ({ children }) => {
  const { user, isAuthenticated } = useAuth();
  const { viewMode, selectedTeam } = useView();
  const [receivedNotifications, setReceivedNotifications] = useState<ShareInvite[]>([]);
  const [sentNotifications, setSentNotifications] = useState<ShareInvite[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const userId = user?.username || '';
  const teamId = viewMode === 'team' ? selectedTeam?.id : undefined;
  const scopeKey = JSON.stringify([isAuthenticated, userId, viewMode, teamId]);
  const currentScope = useRef(scopeKey);
  currentScope.current = scopeKey;
  const scopeRequests = useRef(new AbortController());
  const beginRefresh = useLatestRequest();

  useEffect(() => {
    const owned = new AbortController();
    scopeRequests.current = owned;
    return () => owned.abort();
  }, [scopeKey]);

  const refreshNotifications = useCallback(async () => {
    const signal = beginRefresh();
    const key = scopeKey;
    const active = () => !signal.aborted && currentScope.current === key;
    if (!isAuthenticated || !userId || (viewMode === 'team' && !teamId)) {
      setIsLoading(false);
      return;
    }
    setIsLoading(true);
    setError(null);
    try {
      const [received, sent] = await Promise.all([
        listShares('received', undefined, 0, 100, teamId, signal),
        listShares('sent', undefined, 0, 100, teamId, signal),
      ]);
      if (!active()) return;
      setReceivedNotifications(received.invites);
      setSentNotifications(sent.invites);
    } catch (failure) {
      if (active()) setError(failure instanceof Error ? failure.message : 'Failed to fetch notifications');
    } finally {
      if (active()) setIsLoading(false);
    }
  }, [beginRefresh, isAuthenticated, userId, viewMode, teamId, scopeKey]);

  useEffect(() => {
    setReceivedNotifications([]);
    setSentNotifications([]);
    setError(null);
    void refreshNotifications();
    const interval = setInterval(() => { void refreshNotifications(); }, 30000);
    return () => clearInterval(interval);
  }, [refreshNotifications]);

  const mutate = async (operation: (signal: AbortSignal) => Promise<unknown>) => {
    const key = scopeKey;
    const signal = scopeRequests.current.signal;
    const active = () => !signal.aborted && currentScope.current === key;
    setError(null);
    try {
      await operation(signal);
      if (active()) await refreshNotifications();
    } catch (failure) {
      if (!active()) return;
      setError(failure instanceof Error ? failure.message : 'Failed to update invitation');
      throw failure;
    }
  };

  const sendNotification = (request: CreateShareRequest) => mutate(signal => createShare({
    ...request,
    teamId,
    senderIdentityId: teamId || userId,
    senderType: teamId ? 'team' : 'user',
    senderDisplayName: teamId ? selectedTeam?.name?.trim() || teamId : userId,
  }, signal));
  const acceptNotification = (shareId: string) => mutate(signal => acceptShare({ shareId, teamId }, signal));
  const declineNotification = (shareId: string) => mutate(signal => declineShare({ shareId, teamId }, signal));
  const pendingNotificationsCount = receivedNotifications.filter(item => item.status === 'pending' && !item.is_expired).length;

  return <NotificationContext.Provider value={{
    receivedNotifications, sentNotifications, isLoading, error,
    pendingNotificationsCount, hasUnreadNotifications: pendingNotificationsCount > 0,
    refreshNotifications, sendNotification, acceptNotification, declineNotification,
    clearError: () => setError(null),
  }}>{children}</NotificationContext.Provider>;
};

export const useNotifications = (): NotificationContextType => {
  const context = useContext(NotificationContext);
  if (context === undefined) throw new Error('useNotifications must be used within a NotificationProvider');
  return context;
};
