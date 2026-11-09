import { QueryClient, type QueryFunction } from '@tanstack/react-query';
import api from './axiosAgentConfig';

const axiosQueryFn: QueryFunction<unknown> = async ({ queryKey }) => {
  const [url, params] = queryKey as [string, Record<string, unknown>?];
  const response = await api.get(url, params ? { params } : undefined);
  return response.data;
};

export const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      queryFn: axiosQueryFn,
      staleTime: 5 * 60_000,
      retry: 1,
      refetchInterval: false,
      refetchOnWindowFocus: false,
    },
    mutations: { retry: false },
  },
});
