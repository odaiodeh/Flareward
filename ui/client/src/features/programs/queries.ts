import { useInfiniteQuery } from '@tanstack/react-query';
import { listProgramRevisions } from '@/api/programs';

export function useProgramRevisions(id: string, scope: string, teamId?: string, enabled = true) {
  const query = useInfiniteQuery({
    queryKey: ['program-revisions', scope, id], enabled: enabled && !!id,
    initialPageParam: undefined as number | undefined,
    queryFn: ({ pageParam, signal }) => listProgramRevisions(id, pageParam, teamId, signal),
    getNextPageParam: page => page.next_cursor ?? undefined,
  });
  return { ...query, revisions: query.data?.pages.flatMap(page => page.revisions) ?? [] };
}
