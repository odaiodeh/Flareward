/** Production clients use canonical platform routes and authenticated-human scope. */
import assert from 'node:assert/strict';
import api from '../client/src/http/axiosAgentConfig';
import { checkAdminAccess, getAdminConfig, updateAdminConfigSection } from '../client/src/api/adminConfig';
import { checkUserApproval, approveUser } from '../client/src/api/termsApproval';

export default async function administrationClients() {
  const endpoint = process.env.FLAREWARD_TEST_UI_API_URL;
  const cookie = process.env.FLAREWARD_TEST_UI_ADMIN_COOKIE;
  assert.ok(endpoint && cookie);
  api.defaults.baseURL = endpoint;
  api.defaults.headers.common.Cookie = cookie;
  assert.equal((await checkAdminAccess()).is_admin, true);
  const section = (await getAdminConfig()).categories.flatMap(category => category.sections)
    .find(section => section.key === 'admin_users');
  assert.ok(section);
  const values = Object.fromEntries(section.fields.map(field => [field.key, field.value]));
  assert.equal((await updateAdminConfigSection(section.key, values, section.revision)).status, 'success');
  await assert.rejects(() => updateAdminConfigSection(section.key, values, section.revision));
  await approveUser();
  assert.equal((await checkUserApproval()).approved, true);
  console.log('Administration and consent production clients passed');
}
