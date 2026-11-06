import React, { useCallback, useRef } from 'react';
import type { ProgramDescriptor } from '@/api/programs';
import ResourceBundleField from '@/components/resources/ResourceBundleField';
import SchemaValue, { type SchemaField } from '@/components/schema/SchemaValue';
import { isRecord } from '@/lib/json';
import type { JsonObject } from '@shared/json';
import ExecutionSelectionFields from './ExecutionSelectionFields';

/** Program configuration composes generic forms with the resource capture adapter. */
export default function ProgramConfiguration({ descriptor, config, onChange, disabled, scope, teamId, profiles, environments, onBusyChange }: {
  descriptor: ProgramDescriptor; config: JsonObject; onChange: (value: JsonObject) => void; disabled: boolean;
  scope: string; teamId?: string; onBusyChange: (busy: boolean) => void;
  profiles: string[]; environments: string[];
}) {
  const pending = useRef(new Set<string>());
  const pendingChange = useCallback((path: string, busy: boolean) => {
    if (busy) pending.current.add(path); else pending.current.delete(path);
    onBusyChange(pending.current.size > 0);
  }, [onBusyChange]);
  return <SchemaValue schema={descriptor.configuration_schema} label="Configuration" value={config} disabled={disabled} onChange={next => { if (isRecord(next)) onChange(next as JsonObject); }} renderField={field => {
    if (field.schema.title === 'ElementBundle') return <CapturedConfiguration key={JSON.stringify([scope, teamId, field.path, isRecord(field.value) ? field.value.content_digest : null])} {...field} scope={scope} teamId={teamId} onPendingChange={pendingChange} />;
    if (field.schema.title === 'ExecutionSelection') return <ExecutionSelectionFields value={isRecord(field.value) ? field.value : {}} profiles={profiles} environments={environments} disabled={field.disabled} label={field.label} onChange={selection => field.onChange({ ...selection })} />;
    return null;
  }} />;
}

function CapturedConfiguration({ onPendingChange, ...field }: SchemaField & {
  scope: string; teamId?: string; onPendingChange: (path: string, pending: boolean) => void;
}) {
  const pendingChange = useCallback((busy: boolean) => onPendingChange(field.path, busy), [field.path, onPendingChange]);
  return <ResourceBundleField {...field} onPendingChange={pendingChange} />;
}
