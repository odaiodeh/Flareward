import React, { useState } from 'react';
import type { DependencyInterface, ProgramRef, ProgramSummary, ProgramTarget } from '@/api/programs';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import ProgramPicker from './ProgramPicker';
import { programTargetLabel } from './authoring';

export default function ProgramDependencies({ children, onChange, programs, teamId, scope, disabled, declarations, resolving, resolutionIssue }: {
  children: Record<string, ProgramTarget>; onChange: (children: Record<string, ProgramTarget>) => void;
  programs: ProgramSummary[]; teamId?: string; scope: string; disabled: boolean;
  declarations?: Record<string, DependencyInterface>; resolving?: boolean; resolutionIssue?: string;
}) {
  const [adding, setAdding] = useState(false);
  const [alias, setAlias] = useState('body');
  const [pending, setPending] = useState<ProgramRef>();
  const names = [...new Set([...Object.keys(declarations ?? {}), ...Object.keys(children)])];
  return <section className="space-y-3"><h3 className="font-medium">Program dependencies</h3>
    <p className="text-xs text-muted-foreground">Bind the dependency names declared by this program to published programs. Revisions stay pinned until you explicitly replace them.</p>
    {resolving && <p role="status" className="text-xs text-muted-foreground">Resolving dependencies from configuration…</p>}
    {resolutionIssue && <p role="status" className="text-xs text-muted-foreground">{resolutionIssue}</p>}
    {names.map(name => {
      const reference = Object.hasOwn(children, name) ? children[name] : undefined;
      const declaration = declarations && Object.hasOwn(declarations, name) ? declarations[name] : undefined;
      return <fieldset key={name} className="space-y-3 rounded border p-3" disabled={disabled}>
      <legend className="px-1 text-sm font-medium">{name}</legend>
      {declaration && <p className="text-xs text-muted-foreground">Required dependency{reference ? ' · binding selected' : ' · select a Program'}</p>}
      {reference && !('program_id' in reference) && <p className="text-sm">{programTargetLabel(reference, programs)} — saved within this Program.</p>}
      <ProgramPicker value={reference && 'program_id' in reference ? reference : undefined} onChange={value => onChange({ ...children, [name]: value })} programs={programs} teamId={teamId} scope={scope} disabled={disabled} label={`${!reference || 'program_id' in reference ? 'Program' : 'Replace inline body with published program'} for ${name}`} />
      {declaration && <details className="text-sm"><summary>Expected call contract</summary><p className="my-2 text-xs text-muted-foreground">Declared request projection and consumed results. Publication checks the selected Program.</p><pre className="max-h-56 overflow-auto text-xs">{JSON.stringify(declaration, null, 2)}</pre></details>}
      {reference && <Button variant="ghost" type="button" onClick={() => { const next = { ...children }; delete next[name]; onChange(next); }}>Remove binding</Button>}
    </fieldset>;
    })}
    {adding ? <div className="space-y-3 rounded border p-3"><label className="block text-sm">Dependency name<Input className="text-inherit" aria-label="New dependency name" value={alias} disabled={disabled} onChange={event => setAlias(event.target.value)} /></label>
      <ProgramPicker value={pending} onChange={setPending} programs={programs} teamId={teamId} scope={scope} disabled={disabled} label="Dependency program" />
      <Button type="button" variant="outline" disabled={disabled || !pending || !alias.trim() || Object.hasOwn(children, alias.trim())} onClick={() => {
        if (pending) { onChange({ ...children, [alias.trim()]: pending }); setAdding(false); setPending(undefined); setAlias(''); }
      }}>Use this program</Button>
      <Button type="button" variant="ghost" disabled={disabled} onClick={() => setAdding(false)}>Cancel</Button>
    </div> : <Button type="button" variant="outline" disabled={disabled} onClick={() => setAdding(true)}>Add program dependency</Button>}
  </section>;
}
