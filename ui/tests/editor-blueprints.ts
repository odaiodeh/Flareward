/** Existing editor clients author a saved-reference blueprint and execute its native snapshot. */
import assert from 'node:assert/strict';
import { dump } from 'js-yaml';
import axios from '../client/src/http/axiosAgentConfig';
import {
  deleteBlueprint, fetchBlueprints, fetchBlueprintSummaries, fetchResolvedBlueprint,
  fetchResolvedBlueprints, getBlueprintDraftSchema, getBlueprintInfo, getPromptShortcuts,
  saveBlueprint, setBlueprintMetadata, setPromptShortcuts, updateBlueprint, validateBlueprint,
  validateDraft,
  previewBlueprintPlacement,
} from '../client/src/api/blueprints';
import { createResource, deleteResource, updateResource } from '../client/src/api/resources';
import { applyWorkflowPlacement } from '../client/src/lib/workflow-placement';

const endpoint = process.env.FLAREWARD_TEST_UI_API_URL;
assert.ok(endpoint, 'FLAREWARD_TEST_UI_API_URL must identify an isolated native test API');
axios.defaults.baseURL = endpoint;

export default async function verifyEditorBlueprints() {
  const model = await createResource({
    category: 'llms', type: 'mock', name: 'Editor blueprint model',
    config: { base_url: 'http://unused.invalid', api_key: 'blueprint-client-private' },
  });
  let nodeId: string | undefined;
  let blueprintId: string | undefined;
  try {
    const node = await createResource({
      category: 'nodes', type: 'mock_agent_node', name: 'Editor blueprint agent',
      config: { llm: `$ref:${model.rid}` },
      execution: { profile: 'process' },
    });
    nodeId = node.rid;
    const draft = applyWorkflowPlacement({
      name: 'Editor saved-reference workflow', description: 'Native authoring via existing UI clients',
      nodes: [{ rid: `$ref:${node.rid}`, name: node.name }], plan: [{ uid: 'respond', node: `$ref:${node.rid}` }],
    }, { execution_profile: 'process', environments: {}, steps: { respond: { execution: {} } } });
    assert.deepEqual(await previewBlueprintPlacement(draft), {
      default_profile: 'process', environments: {}, invocations: [{
        step_uid: 'respond', category: 'nodes', profile: 'process', environment: null,
        binding_scope: 'invocation',
      }],
    });
    const source = dump(draft);
    assert.ok((await getBlueprintDraftSchema()).properties.nodes);
    assert.equal((await validateDraft(source)).blueprint_id, 'draft');
    const created = await saveBlueprint(source);
    blueprintId = created.blueprint_id;
    assert.equal(created.status, 'success');
    assert.equal((await getBlueprintInfo(blueprintId)).spec_dict.nodes[0].rid, `$ref:${node.rid}`);
    assert.ok((await fetchBlueprints()).some(item => item.blueprint_id === blueprintId));
    const summary = (await fetchBlueprintSummaries()).find(item => item.blueprint_id === blueprintId);
    assert.equal(summary?.name, draft.name);
    assert.equal(summary?.user_id, 'owner');
    assert.ok(!JSON.stringify(summary).includes('spec_dict'));
    const resolved = await fetchResolvedBlueprint(blueprintId);
    assert.ok(resolved);
    assert.equal(resolved.spec_dict.llms[0].config.api_key, '********');
    assert.equal(resolved.spec_dict.nodes[0].config.llm, `$ref:${model.rid}`);
    assert.deepEqual(resolved.spec_dict.nodes[0].execution, { profile: 'process' });
    assert.ok(!JSON.stringify(resolved).includes('blueprint-client-private'));
    assert.ok((await fetchResolvedBlueprints()).some(item => item.blueprint_id === blueprintId));
    const shortcuts = await setPromptShortcuts(blueprintId, [{ text: 'Run editor workflow' }]);
    assert.equal(shortcuts.prompts.length, 1);
    assert.deepEqual(await getPromptShortcuts(blueprintId), shortcuts);
    assert.equal((await validateBlueprint({ blueprintId })).blueprint_id, blueprintId);
    const beforeEdit = await getBlueprintInfo(blueprintId);
    assert.ok(beforeEdit.version);
    const edited = await updateBlueprint(blueprintId, dump({ ...draft, name: 'Edited editor workflow' }),
      undefined, beforeEdit.version);
    assert.equal(edited.version, beforeEdit.version + 1);
    await assert.rejects(updateBlueprint(blueprintId, source, undefined, beforeEdit.version), error =>
      !!error && typeof error === 'object' && 'response' in error &&
      (error.response as { status: number }).status === 409,
    );
    assert.deepEqual((await getBlueprintInfo(blueprintId)).spec_dict.prompt_shortcuts, shortcuts.prompts);
    await setBlueprintMetadata(blueprintId, { usageScope: 'private' });
    assert.equal((await getBlueprintInfo(blueprintId)).metadata.usageScope, 'private');

    // Prove the editor's saved draft feeds the native execution foundation.
    const imported = await axios.put('/programs/editor-authored/blueprint', { blueprint_id: blueprintId });
    assert.equal(imported.data.definition.execution_profile, 'process');
    assert.equal(imported.data.definition.implementation.steps[0].execution.profile, null);
    const bindings = Object.fromEntries(Object.keys(imported.data.definition.input_schema.properties).map(
      name => [name, { kind: 'path', path: [name] }],
    ));
    const published = await axios.post('/programs/editor-authored/revisions', { expected_version: imported.data.version });
    assert.equal(published.data.revision, 1);
    await updateResource({
      resourceId: node.rid, config: node.cfg_dict, expected_version: node.version,
      execution: { profile: 'thread' },
    });
    // The revision keeps the profile captured at publication after authoring data changes.
    const pinned = await axios.get('/programs/editor-authored/revisions/1');
    assert.equal(pinned.data.definition.execution_profile, 'process');
    assert.equal(pinned.data.definition.implementation.steps[0].execution.profile, null);
    const session = await axios.post('/sessions', {
      program: { program_id: 'editor-authored', revision: 1 }, blueprint_id: blueprintId,
      interaction: 'conversation', input_bindings: bindings, output_bindings: bindings,
    });
    const sessionId = encodeURIComponent(session.data.run_id);
    await axios.post(`/sessions/${sessionId}/executions`, {
      execution_id: 'editor-turn', inputs: { user_prompt: 'from the UI client' },
    });
    const result = await axios.get('/executions/editor-turn/result');
    assert.equal(result.data.phase, 'completed');
    assert.deepEqual(result.data.result.nodes_output, { respond: 'Mock echo: from the UI client' });
    assert.equal((await axios.get(`/sessions/${sessionId}`)).data.graph_state.nodes_output.respond,
      'Mock echo: from the UI client');
    assert.ok(!JSON.stringify(result.data).includes('blueprint-client-private'));
  } finally {
    if (blueprintId) await deleteBlueprint(blueprintId);
    if (nodeId) await deleteResource(nodeId);
    await deleteResource(model.rid);
  }
  console.log('Existing UI blueprint clients passed against native FastAPI');
}
