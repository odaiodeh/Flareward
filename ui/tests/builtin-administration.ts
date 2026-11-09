/** Real production clients preserve versioning, private fields and human lease authority. */
import assert from 'node:assert/strict';
import axios from '../client/src/http/axiosAgentConfig';
import {
  acquireBuiltinEditLock, configureBuiltin, createBuiltin, deleteBuiltin, getBuiltin,
  getBuiltinSchema, getBuiltinUserConfig, heartbeatBuiltinEditLock, listBuiltins,
  previewBuiltinCascade, releaseBuiltinEditLock, toggleBuiltinVisibility, updateBuiltin,
} from '../client/src/api/resources';

export default async function builtinClients() {
  const endpoint = process.env.FLAREWARD_TEST_UI_API_URL;
  const admin = process.env.FLAREWARD_TEST_UI_ADMIN_COOKIE;
  const reader = process.env.FLAREWARD_TEST_UI_OWNER_COOKIE;
  assert.ok(endpoint && admin && reader);
  axios.defaults.baseURL = endpoint;
  axios.defaults.headers.common.Cookie = admin;
  const root = process.env.FLAREWARD_TEST_UI_ROOT_RESOURCE;
  assert.ok(root);
  let operation = await createBuiltin({ category: 'operations', type: 'platform_text_operation', name: 'Placed curated operation', config: { dependency: '$ref:' + root }, execution: { profile: 'process' } });
  try {
    assert.equal(operation.execution?.profile, 'process');
    operation = await updateBuiltin({ resourceId: operation.rid, expectedVersion: operation.version, execution: { profile: 'thread' } });
    assert.equal(operation.execution?.profile, 'thread');
    assert.equal((await getBuiltin(operation.rid)).execution?.profile, 'thread');
  } finally {
    await deleteBuiltin(operation.rid, operation.version);
  }
  const model = await createBuiltin({ category: 'llms', type: 'mock', name: 'Client curated model', config: { api_key: 'client-base-private', base_url: 'http://unused.invalid' } });
  let version = model.version;
  try {
    assert.ok(!JSON.stringify(model).includes('client-base-private'));
    assert.ok((await listBuiltins()).resources.some(row => row.rid === model.rid));
    assert.equal((await getBuiltin(model.rid)).version, version);
    assert.equal((await acquireBuiltinEditLock(model.rid)).acquired, true);
    await heartbeatBuiltinEditLock(model.rid);
    const changed = await updateBuiltin({ resourceId: model.rid, expectedVersion: version, name: 'Changed client model', config: model.cfg_dict });
    assert.equal(changed.version, 2);
    await assert.rejects(updateBuiltin({ resourceId: model.rid, expectedVersion: version, name: 'Stale model' }));
    version = changed.version;
    assert.deepEqual(await previewBuiltinCascade(model.rid), []);
    const published = await toggleBuiltinVisibility({ resourceId: model.rid, expectedVersion: version, availableToAll: true });
    version = published.version;
    assert.equal(published.visibility, 'public');
    await releaseBuiltinEditLock(model.rid);
    axios.defaults.headers.common.Cookie = reader;
    await assert.rejects(listBuiltins());
    assert.ok((await getBuiltinSchema(model.rid)).properties.api_key);
    assert.equal(await getBuiltinUserConfig({ resourceId: model.rid }), null);
    const configured = await configureBuiltin({ resourceId: model.rid, config: { api_key: 'client-overlay-private' } });
    assert.equal(configured.user_configured, true);
    assert.ok(!JSON.stringify(configured).includes('client-overlay-private'));
    assert.ok((await getBuiltinUserConfig({ resourceId: model.rid }))?.api_key);
    axios.defaults.headers.common.Cookie = admin;
  } finally {
    axios.defaults.headers.common.Cookie = admin;
    await releaseBuiltinEditLock(model.rid);
    await deleteBuiltin(model.rid, version);
  }
  console.log('Curated library production clients passed');
}
