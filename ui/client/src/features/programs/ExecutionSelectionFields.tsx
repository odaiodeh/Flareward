import React from 'react';
import type { ExecutionSelection } from '@/api/programs';

/** Placement controls are shared by work calls and condition invocations. */
export default function ExecutionSelectionFields({ value, profiles, environments, disabled, label, onChange }: {
  value: ExecutionSelection; profiles: string[]; environments: string[]; disabled: boolean;
  label: string; onChange: (selection: ExecutionSelection) => void;
}) {
  return <div className="grid gap-3 sm:grid-cols-2"><label className="text-sm">{label} profile<select aria-label={`${label} profile`} className="block w-full rounded border bg-background p-2" disabled={disabled || !!value.environment} value={value.profile ?? ''} onChange={event => onChange(event.target.value ? { profile: event.target.value } : {})}>
    <option value="">Workflow / platform default</option>{value.profile && !profiles.includes(value.profile) && <option value={value.profile}>{value.profile} (unavailable)</option>}{profiles.map(profile => <option key={profile}>{profile}</option>)}
  </select></label><label className="text-sm">{label} environment<select aria-label={`${label} environment`} className="block w-full rounded border bg-background p-2" disabled={disabled} value={value.environment ?? ''} onChange={event => onChange(event.target.value ? { environment: event.target.value } : {})}>
    <option value="">No retained environment</option>{value.environment && !environments.includes(value.environment) && <option value={value.environment}>{value.environment} (unavailable)</option>}{environments.map(name => <option key={name}>{name}</option>)}
  </select></label></div>;
}
