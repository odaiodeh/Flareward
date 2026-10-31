/** Actual dialog and clients; only identity issuance and infrastructure are test fixtures. */
import React, { useEffect, useState } from 'react';
import { createRoot } from 'react-dom/client';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { AuthProvider, useAuth } from '../client/src/contexts/AuthContext';
import SaveBlueprintModal from '../client/src/components/agentic-ai/graphs/SaveBlueprintModal';
import axios from '../client/src/http/axiosAgentConfig';
import { api as authApi } from '../client/src/http/authClient';
import { api as settingsApi } from '../client/src/http/queryClient';
import { listAllResources } from '../client/src/api/resources';
import { getBlueprintInfo, saveBlueprint, updateBlueprint } from '../client/src/api/blueprints';
import { applyWorkflowPlacement } from '../client/src/lib/workflow-placement';
import type { WorkflowPlacement, YamlFlowState } from '../client/src/types/graph';
import '../client/src/index.css';

axios.defaults.baseURL = '/api';
authApi.defaults.baseURL = '/fixture';
settingsApi.defaults.baseURL = '/fixture';

function BrowserFixture() {
  const { user, isAuthenticated, isLoading } = useAuth();
  const [flow, setFlow] = useState<YamlFlowState | null>(null);
  const [open, setOpen] = useState(false);
  const [savedId, setSavedId] = useState<string>();
  const [version, setVersion] = useState<number>();
  const [message, setMessage] = useState('');
  useEffect(() => {
    if (!isAuthenticated) return;
    let stale = false;
    listAllResources({}).then(resources => {
      if (stale) return;
      const node = (name: string) => resources.find(resource => resource.name === name)!;
      const work = node('Browser work'), finish = node('Browser finish'), condition = node('Browser condition');
      setFlow({ name: 'Browser placement workflow', execution_profile: 'thread', environments: {},
        nodes: [work, finish].map(resource => ({ rid: `$ref:${resource.rid}`, name: resource.name })),
        conditions: [{ rid: `$ref:${condition.rid}`, name: condition.name }],
        plan: [{ uid: 'work', node: `$ref:${work.rid}`, exit_condition: `$ref:${condition.rid}`,
          branches: { true: 'finish', false: 'finish' } },
        { uid: 'finish', node: `$ref:${finish.rid}` }],
      });
      setOpen(true);
    }).catch(() => setMessage('Fixture resources failed to load'));
    return () => { stale = true; };
  }, [isAuthenticated]);
  async function save(name: string, description: string, _prompts: unknown, placement: WorkflowPlacement) {
    if (!flow) return;
    try {
      const spec = { ...applyWorkflowPlacement(flow, placement), name, description };
      const result = savedId ? await updateBlueprint(savedId, JSON.stringify(spec), undefined, version)
        : await saveBlueprint(JSON.stringify(spec));
      const id = savedId ?? result.blueprint_id;
      const stored = await getBlueprintInfo(id);
      setFlow(stored.spec_dict as unknown as YamlFlowState);
      setVersion(stored.version); setSavedId(id); setOpen(false);
      setMessage(`Saved and reloaded version ${stored.version}`);
    } catch { setMessage('Save failed'); }
  }
  return <main className="dark min-h-screen bg-gray-950 p-8 text-white">
    <h1 className="text-xl">Placement browser verification</h1>
    <p>{isLoading ? 'Signing in' : isAuthenticated ? `Authenticated as ${user?.username}` : 'Authentication required'}</p>
    <p role="status">{message}</p>
    {flow && <>
      <button onClick={() => setOpen(true)}>Reopen saved workflow</button>
      <pre aria-label="Saved placement">{JSON.stringify({ execution_profile: flow.execution_profile,
        environments: flow.environments, plan: flow.plan }, null, 2)}</pre>
      <SaveBlueprintModal isOpen={open} onClose={() => setOpen(false)} onSave={save}
        flow={flow} currentName={flow.name} currentDescription={flow.description}
        isEditMode={!!savedId} />
    </>}
  </main>;
}

createRoot(document.getElementById('root')!).render(
  <QueryClientProvider client={new QueryClient()}><AuthProvider><BrowserFixture /></AuthProvider></QueryClientProvider>,
);
