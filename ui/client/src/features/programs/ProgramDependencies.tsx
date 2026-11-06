import React, { useState } from 'react';
import type { ProgramRef, ProgramSummary, ProgramTarget } from '@/api/programs';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import ProgramPicker from './ProgramPicker';
import { programTargetLabel } from './authoring';

export default function ProgramDependencies({ children, onChange, programs, teamId, scope, disabled }: {
  children: Record<string, ProgramTarget>; onChange: (children: Record<string, ProgramTarget>) => void;
  programs: ProgramSummary[]; teamId?: string; scope: string; disabled: boolean;
}) {
  const [adding, setAdding] = useState(false);
  const [alias, setAlias] = useState('body');
  const [pending, setPending] = useState<ProgramRef>();
  return <section className="space-y-3"><h3 className="font-medium">Program dependencies</h3>
    <p className="text-xs text-muted-foreground">Bind the dependency names declared by this program to published programs. Revisions stay pinned until you explicitly replace them.</p>
    {Object.entries(children).map(([name, reference]) => <fieldset key={name} className="space-y-3 rounded border p-3" disabled={disabled}>
      <h4 className="text-sm font-medium">{name}</h4>
      {!('program_id' in reference) && <p className="text-sm">{programTargetLabel(reference, programs)} — saved within this Program.</p>}
      <ProgramPicker value={'program_id' in reference ? reference : undefined} onChange={value => onChange({ ...children, [name]: value })} programs={programs} teamId={teamId} scope={scope} disabled={disabled} label={`${'program_id' in reference ? 'Program' : 'Replace inline body with published program'} for ${name}`} />
      <Button variant="ghost" type="button" onClick={() => { const next = { ...children }; delete next[name]; onChange(next); }}>Remove dependency</Button>
    </fieldset>)}
    {adding ? <div className="space-y-3 rounded border p-3"><label className="block text-sm">Dependency name<Input className="text-inherit" aria-label="New dependency name" value={alias} disabled={disabled} onChange={event => setAlias(event.target.value)} /></label>
      <ProgramPicker value={pending} onChange={setPending} programs={programs} teamId={teamId} scope={scope} disabled={disabled} label="Dependency program" />
      <Button type="button" variant="outline" disabled={disabled || !pending || !alias.trim() || Object.hasOwn(children, alias.trim())} onClick={() => {
        if (pending) { onChange({ ...children, [alias.trim()]: pending }); setAdding(false); setPending(undefined); setAlias(''); }
      }}>Use this program</Button>
      <Button type="button" variant="ghost" disabled={disabled} onClick={() => setAdding(false)}>Cancel</Button>
    </div> : <Button type="button" variant="outline" disabled={disabled} onClick={() => setAdding(true)}>Add program dependency</Button>}
  </section>;
}
