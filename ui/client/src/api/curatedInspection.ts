import axios from '@/http/axiosAgentConfig';
import type { ElementValidationResult } from '@/types/validation';

export interface CuratedInspection {
  mode: 'curated_base';
  observed_at: string;
  results: ElementValidationResult[];
}

export async function validateCuratedResources(
  resourceIds: string[], signal?: AbortSignal,
): Promise<CuratedInspection> {
  return (await axios.post<CuratedInspection>('/administration/resources/validation', {
    resource_ids: resourceIds,
  }, { signal })).data;
}
