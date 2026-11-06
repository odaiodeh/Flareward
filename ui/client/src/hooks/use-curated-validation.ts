import { useQuery } from '@tanstack/react-query';
import { validateCuratedResources } from '@/api/curatedInspection';
import { useAuth } from '@/contexts/AuthContext';
import type { ValidationStatus } from '@/contexts/AgenticAIContext';

/** Curated-base results never enter the selected owner's overlay-validation cache. */
export function useCuratedValidation(resources: Array<{ rid: string; version: number }>) {
  const { user } = useAuth();
  const selection = resources.map(({ rid, version }) => [rid, version] as const)
    .sort(([left], [right]) => left.localeCompare(right));
  const query = useQuery({
    queryKey: ['curated-base-validation', user?.username || user?.sub, selection],
    queryFn: async ({ signal }) => {
      const results = [];
      for (let offset = 0; offset < selection.length; offset += 100) {
        const report = await validateCuratedResources(
          selection.slice(offset, offset + 100).map(([rid]) => rid), signal,
        );
        if (report.mode !== 'curated_base') throw new Error('Unexpected inspection view');
        results.push(...report.results);
      }
      return new Map(results.map(result => [result.element_rid, result]));
    },
    enabled: !!user?.is_admin && selection.length > 0,
    staleTime: 60_000,
    retry: false,
  });
  return {
    getValidationResult: (rid: string) => query.isError ? null : query.data?.get(rid) ?? null,
    getValidationStatus: (rid: string): ValidationStatus | 'unavailable' => {
      if (query.isError) return 'unavailable';
      if (query.isFetching) return 'loading';
      const result = query.data?.get(rid);
      return result ? (result.is_valid ? 'valid' : 'invalid') : 'unavailable';
    },
    revalidate: () => query.refetch(),
  };
}
