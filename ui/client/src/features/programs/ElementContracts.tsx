import React from 'react';
import { useQuery } from '@tanstack/react-query';
import { catalogService } from '@/api/catalog';
import { programError } from './authoring';

export default function ElementContracts({ category, type, scope }: { category: string; type: string; scope: string }) {
  const contracts = useQuery({
    queryKey: ['program-element-contracts', scope, category, type],
    queryFn: ({ signal }) => catalogService.fetchElementContracts(category, type, signal),
  });
  return <details className="text-sm"><summary>Element input and output contracts</summary>
    {contracts.error && <p role="alert" className="text-destructive">{programError(contracts.error)}</p>}
    {contracts.data && <pre className="max-h-48 overflow-auto text-xs">{JSON.stringify(contracts.data, null, 2)}</pre>}
  </details>;
}
