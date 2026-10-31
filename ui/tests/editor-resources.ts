/** Exercise production API clients against a separately running native API. */
import assert from 'node:assert/strict';
import axios from '../client/src/http/axiosAgentConfig';
import { catalogService } from '../client/src/api/catalog';
import {
  createResource, deleteResource, getElementSpec, getResource, getResourceSchema,
  listAllResources, updateResource,
} from '../client/src/api/resources';

const endpoint = process.env.UNIFAI_TEST_UI_API_URL;
assert.ok(endpoint, 'UNIFAI_TEST_UI_API_URL must identify an isolated native test API');
axios.defaults.baseURL = endpoint;

export default async function verifyEditorResources() {
  const catalog = await catalogService.fetchAllElements();
  assert.ok(catalog.elements.nodes.some(element => element.type === 'codex_agent_node'));
  assert.ok(!(await catalogService.fetchCategories()).includes('sandboxes'));
  const schema = await getElementSpec('nodes', 'codex_agent_node');
  assert.ok(schema.config_schema.required?.includes('model'));
  const envelope = await getResourceSchema();
  assert.ok(envelope.properties.name);
  assert.deepEqual(await catalogService.fetchExecutionProfiles(), {
    profiles: ['process', 'thread'], default_profile: 'thread', environment_profiles: [],
  });
  const placed = await createResource({
    category: 'nodes', type: 'codex_agent_node', name: 'Placed coding agent',
    config: { model: 'fixture-model' }, execution: { profile: 'process' },
  });
  try {
    assert.deepEqual(placed.execution, { profile: 'process' });
    assert.ok(!('execution' in placed.cfg_dict));
    assert.deepEqual((await getResource(placed.rid)).execution, placed.execution);
    assert.deepEqual((await listAllResources({ category: 'nodes' })).find(
      resource => resource.rid === placed.rid,
    )?.execution, placed.execution);
    const retained = await updateResource({
      resourceId: placed.rid, config: placed.cfg_dict, expected_version: placed.version,
      name: 'Renamed without changing environment',
    });
    assert.deepEqual(retained.execution, placed.execution);
    await assert.rejects(updateResource({
      resourceId: placed.rid, config: placed.cfg_dict, expected_version: placed.version,
      execution: { profile: 'thread' },
    }), error => !!error && typeof error === 'object' && 'response' in error &&
      (error.response as { status: number }).status === 409);
    const reset = await updateResource({
      resourceId: placed.rid, config: retained.cfg_dict, expected_version: retained.version,
      execution: { profile: null },
    });
    assert.deepEqual(reset.execution, { profile: null });
    assert.ok(!('execution' in reset.cfg_dict));
  } finally {
    await deleteResource(placed.rid);
  }
  await assert.rejects(createResource({
    category: 'invalid', type: 'mock', name: 'Invalid editor input',
    config: { api_key: 'do-not-echo-validation-input' },
  }), error => {
    assert.ok(error && typeof error === 'object' && 'response' in error);
    const response = error.response as { status: number; data: { error: string } };
    assert.equal(response.status, 422);
    assert.ok(response.data.error);
    assert.ok(!JSON.stringify(response.data).includes('do-not-echo-validation-input'));
    return true;
  });

  const created = await createResource({
    category: 'llms', type: 'mock', name: 'TypeScript editor model',
    config: { base_url: 'http://unused.invalid', api_key: 'typescript-private-value' },
  });
  try {
    assert.ok(!JSON.stringify(created).includes('typescript-private-value'));
    assert.equal((await getResource(created.rid)).name, created.name);
    const listed = await listAllResources({ category: 'llms', type: 'mock' });
    assert.ok(listed.some(item => item.rid === created.rid));
    const edited = await updateResource({
      resourceId: created.rid, config: created.cfg_dict, name: 'Edited by TypeScript client',
    });
    assert.equal(edited.version, 2);
    assert.equal((await getResource(created.rid)).name, 'Edited by TypeScript client');
  } finally {
    await deleteResource(created.rid);
  }
  await assert.rejects(getResource(created.rid), error =>
    !!error && typeof error === 'object' && 'response' in error &&
    (error.response as { status: number; data: { error: string } }).status === 404 &&
    (error.response as { data: { error: string } }).data.error === 'Resource not found',
  );
  console.log('Existing UI catalog and resource clients passed against native FastAPI');
}

