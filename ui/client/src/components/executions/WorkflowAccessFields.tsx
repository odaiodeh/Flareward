import React from 'react';
import { useQuery } from '@tanstack/react-query';
import type { JsonObject } from '@shared/json';
import type { WorkflowAccess } from '@/api/programs';
import { workflowAccessCatalog } from '@/api/workflow-access';
import SchemaValue from '@/components/schema/SchemaValue';
import { initialSchemaInput } from '@/components/schema/schema';
import { Button } from '@/components/ui/button';
import { isRecord } from '@/lib/json';

/** Installed issuers describe their own scopes; nothing is selected implicitly. */
export default function WorkflowAccessFields({ scope, teamId, value, onChange, disabled }: {
  scope: string; teamId?: string; value: WorkflowAccess[];
  onChange: (requirements: WorkflowAccess[]) => void; disabled: boolean;
}) {
  const catalog = useQuery({
    queryKey: ['workflow-access-catalog', scope],
    queryFn: ({ signal }) => workflowAccessCatalog(teamId, signal), retry: false,
  });
  const update = (purpose: string, parameters?: JsonObject) => onChange([
    ...value.filter(item => item.purpose !== purpose),
    ...(parameters ? [{ ...parameters, purpose } as unknown as WorkflowAccess] : []),
  ]);
  return <section aria-label="Workflow permissions" className="space-y-3"><h3 className="font-medium">Workflow permissions</h3>
    <p className="text-sm text-muted-foreground">Choose permissions this execution needs. Approval applies to this invocation and its lease durations. Credentials are provisioned privately.</p>
    {catalog.isPending && <p role="status">Loading available permissions…</p>}
    {catalog.isError && <p role="alert">Permission choices are unavailable. <Button type="button" variant="outline" disabled={disabled} onClick={() => void catalog.refetch()}>Retry permission discovery</Button></p>}
    {catalog.data?.length === 0 && <p className="text-sm text-muted-foreground">No managed workflow permissions are available in this workspace.</p>}
    {catalog.data?.map(descriptor => {
      const selected = value.find(item => item.purpose === descriptor.purpose);
      const { purpose: _, ...parameters } = selected ?? { purpose: descriptor.purpose };
      return <fieldset key={descriptor.purpose} className="space-y-3 rounded border p-3" disabled={disabled}>
        <label className="flex items-start gap-2 text-sm font-medium"><input type="checkbox" aria-label={`Allow ${descriptor.name}`} checked={!!selected} disabled={disabled} onChange={event => {
          const initial = initialSchemaInput(descriptor.request_schema);
          update(descriptor.purpose, event.target.checked && isRecord(initial) ? initial as JsonObject : undefined);
        }} />{descriptor.name}</label><p className="text-xs text-muted-foreground">{descriptor.description}</p>
        {selected && <SchemaValue schema={descriptor.request_schema} label={`${descriptor.name} settings`} value={parameters as JsonObject} disabled={disabled} onChange={next => { if (isRecord(next)) update(descriptor.purpose, next as JsonObject); }} />}
      </fieldset>;
    })}
    {value.filter(item => !catalog.data?.some(descriptor => descriptor.purpose === item.purpose)).map(item => <div key={item.purpose} className="rounded border p-3 text-sm"><p>Selected permission is currently unavailable: {item.purpose}</p><pre className="overflow-auto whitespace-pre-wrap">{JSON.stringify(item, null, 2)}</pre><Button type="button" variant="outline" disabled={disabled} onClick={() => update(item.purpose)}>Remove unavailable permission</Button></div>)}
  </section>;
}
