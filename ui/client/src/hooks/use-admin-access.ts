import { useQuery } from '@tanstack/react-query';
import { useAuth } from '@/contexts/AuthContext';
import { checkAdminAccess } from '@/api/adminConfig';

/**
 * Hook that checks whether the current user is an admin.
 *
 * Returns { isAdmin, isLoading } so consumers can gate UI accordingly.
 */
export function useAdminAccess() {
  const { user, isAuthenticated } = useAuth();

  const { data, isLoading } = useQuery({
    queryKey: ['admin-access', user?.username],
    queryFn: () => checkAdminAccess(),
    enabled: isAuthenticated && !!user?.username,
    staleTime: 5 * 60 * 1000,
    retry: 1,
  });

  return {
    isAdmin: data?.is_admin ?? false,
    isLoading,
  };
}
