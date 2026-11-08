import React, { useCallback, useState } from 'react';
import { useInfiniteQuery, useQuery } from '@tanstack/react-query';
import { getProgramDraft, listPrograms, programImplementations } from '@/api/programs';
import { Button } from '@/components/ui/button';
import { AlertDialog, AlertDialogAction, AlertDialogCancel, AlertDialogContent, AlertDialogDescription, AlertDialogFooter, AlertDialogHeader, AlertDialogTitle } from '@/components/ui/alert-dialog';
import ProgramEditor from '@/features/programs/ProgramEditor';
import ProgramTemplateImport from '@/features/programs/ProgramTemplateImport';
import { programError } from '@/features/programs/authoring';
import { useWorkspaceIdentity, type WorkspaceIdentity } from '@/hooks/use-workspace-identity';
import { useExecutionProfiles } from '@/hooks/use-execution-profiles';

function ProgramWorkspace({ owner, scope }: { owner: WorkspaceIdentity; scope: string }) {
  const [selected, setSelected] = useState<{ id: string; existing: boolean }>();
  const [editorState, setEditorState] = useState({ dirty: false, busy: false });
  const [pending, setPending] = useState<{ id: string; existing: boolean } | 'reload'>();
  const [generation, setGeneration] = useState(0);
  const [importBusy, setImportBusy] = useState(false);
  const editorChanged = useCallback((dirty: boolean, busy: boolean) => setEditorState({ dirty, busy }), []);
  const library = useInfiniteQuery({
    queryKey: ['program-library', scope], initialPageParam: '',
    queryFn: ({ pageParam, signal }) => listPrograms(pageParam, owner.teamId, signal),
    getNextPageParam: page => page.next_cursor ?? undefined,
  });
  const catalog = useQuery({ queryKey: ['program-catalog', scope], queryFn: ({ signal }) => programImplementations(signal) });
  const placement = useExecutionProfiles(owner.teamId);
  const draft = useQuery({
    queryKey: ['program-draft', scope, selected?.id, generation], enabled: !!selected?.existing,
    queryFn: ({ signal }) => getProgramDraft(selected!.id, owner.teamId, signal),
    // Mutable authoring must bypass the shared five-minute discovery cache.
    staleTime: 0,
    refetchOnMount: 'always', refetchOnWindowFocus: false, refetchOnReconnect: false,
  });
  const programs = library.data?.pages.flatMap(page => page.programs) ?? [];
  const error = library.error ?? catalog.error ?? placement.error ?? draft.error;
  const changeView = (next: { id: string; existing: boolean } | 'reload') => {
    if (editorState.busy) return;
    setGeneration(value => value + 1);
    if (next !== 'reload') setSelected(next);
    setEditorState({ dirty: false, busy: false });
  };
  const requestView = (next: { id: string; existing: boolean } | 'reload') => {
    if (editorState.dirty) setPending(next); else changeView(next);
  };
  return <main className="dark-inputs h-full overflow-auto p-6 space-y-5"><div className="flex flex-wrap items-center justify-between gap-3">
    <div><h1 className="text-2xl font-semibold">Programs</h1><p className="text-muted-foreground">Configure reusable work, compose workflows, and run published revisions.</p></div>
    <Button disabled={editorState.busy || importBusy} onClick={() => requestView({ id: crypto.randomUUID(), existing: false })}>Create program</Button>
  </div>
    {error && <p role="alert" className="text-destructive">{programError(error)}</p>}
    <div className="grid gap-6 lg:grid-cols-[260px_1fr]"><aside className="space-y-3 rounded border p-4"><h2 className="font-semibold">Programs library</h2>
      {library.isPending && <p role="status">Loading programs...</p>}
      {!library.isPending && !programs.length && <p className="text-sm text-muted-foreground">No saved programs yet. Create one to configure and reuse it.</p>}
      {programs.map(program => <Button key={program.program_id} disabled={editorState.busy || importBusy} variant={selected?.id === program.program_id ? 'secondary' : 'ghost'} className="h-auto w-full justify-start whitespace-normal text-left" onClick={() => requestView({ id: program.program_id, existing: true })}>
        <span>{program.name}<span className="block text-xs font-normal text-muted-foreground">Draft version {program.draft_version}</span></span>
      </Button>)}
      {library.hasNextPage && <Button variant="outline" disabled={library.isFetchingNextPage} onClick={() => void library.fetchNextPage()}>Load more programs</Button>}
      <Button variant="ghost" onClick={() => void library.refetch()}>Refresh library</Button>
      <ProgramTemplateImport scope={scope} teamId={owner.teamId} disabled={editorState.busy || importBusy} onBusy={setImportBusy} onImported={id => { void library.refetch(); requestView({ id, existing: true }); }} />
    </aside><section className="min-w-0 rounded border p-4">
      {selected ? catalog.data && placement.data && (!selected.existing || draft.isFetchedAfterMount && !draft.isError && draft.data) ?
        <ProgramEditor key={JSON.stringify([selected.id, selected.existing, generation])} id={selected.id} initial={selected.existing ? draft.data : undefined} owner={owner} scope={scope} catalog={catalog.data} profiles={placement.data.profiles} programs={programs} onState={editorChanged} /> :
        <p role="status">{draft.isError ? 'The current draft could not be loaded. Reload before editing.' : 'Loading program...'}</p> : <p className="text-muted-foreground">Open a saved program or create one. Programs can run on their own and be reused inside larger workflows.</p>}
      {selected?.existing && <Button disabled={editorState.busy || importBusy} className="mt-5" variant="ghost" onClick={() => requestView('reload')}>Reload saved draft</Button>}
    </section></div>
    <AlertDialog open={pending !== undefined} onOpenChange={open => { if (!open) setPending(undefined); }}><AlertDialogContent>
      <AlertDialogHeader><AlertDialogTitle>Discard unsaved changes?</AlertDialogTitle><AlertDialogDescription>Your saved draft and published revisions will remain available.</AlertDialogDescription></AlertDialogHeader>
      <AlertDialogFooter><AlertDialogCancel>Keep editing</AlertDialogCancel><AlertDialogAction onClick={() => { if (pending) changeView(pending); setPending(undefined); }}>Discard changes</AlertDialogAction></AlertDialogFooter>
    </AlertDialogContent></AlertDialog>
  </main>;
}

export default function Programs() {
  const owner = useWorkspaceIdentity();
  const scope = JSON.stringify([owner.isTeam, owner.userId, owner.credentialUserId]);
  return <ProgramWorkspace key={scope} owner={owner} scope={scope} />;
}
