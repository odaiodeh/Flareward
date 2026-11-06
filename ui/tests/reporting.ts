/** Production reporting clients preserve root, revision, owner and completion semantics. */
import assert from 'node:assert/strict';
import axios from '../client/src/http/axiosAgentConfig';
import { fetchAgenticStats } from '../client/src/api/agentic';
import { fetchSystemWideStats } from '../client/src/api/systemStats';

export default async function reportingClients() {
  const endpoint = process.env.UNIFAI_TEST_UI_API_URL;
  const owner = process.env.UNIFAI_TEST_UI_OWNER_COOKIE;
  const admin = process.env.UNIFAI_TEST_UI_ADMIN_COOKIE;
  assert.ok(endpoint && owner && admin);
  axios.defaults.baseURL = endpoint;
  axios.defaults.headers.common.Cookie = owner;
  const overview = await fetchAgenticStats();
  assert.equal(overview.activeSessions, 0);
  assert.equal(overview.totalWorkflows, 0);
  await assert.rejects(() => fetchSystemWideStats('today'));
  axios.defaults.headers.common.Cookie = admin;
  const first = await fetchSystemWideStats('today', 0, 1);
  assert.equal(first.total_stats.total_runs, 6);
  assert.equal(first.total_stats.unique_users, 2);
  assert.equal(first.owner_activity.length, 1);
  assert.equal(first.top_owners.length, 2);
  assert.equal(first.top_programs.find(row => row.program_revision === 1)?.program_name, 'Original name');
  assert.equal(first.top_programs.find(row => row.program_revision === 1)?.completion_rate, 75);
  assert.equal(first.status_breakdown.COMPLETED, 3);
  const second = await fetchSystemWideStats('today', 1, 1);
  assert.notEqual(second.owner_activity[0].identity_type, first.owner_activity[0].identity_type);
  assert.equal(second.owner_activity[0].identity_id, first.owner_activity[0].identity_id);
  console.log('Reporting production clients passed');
}
