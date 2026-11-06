import { useQuery } from '@tanstack/react-query';
import { catalogService } from '@/api/catalog';
import { useAuth } from '@/contexts/AuthContext';

export function useExecutionProfiles(teamId?: string) {
  const { user } = useAuth();
  return useQuery({
    queryKey: ['execution-profiles', user?.username, teamId ? 'team' : 'user', teamId ?? user?.username],
    enabled: !!user?.username,
    queryFn: ({ signal }) => catalogService.fetchExecutionProfiles(teamId, signal),
  });
}
