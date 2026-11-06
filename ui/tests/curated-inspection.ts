/** Production clients inspect curated defaults independently of owner overlays. */
import assert from 'node:assert/strict';
import axios from '../client/src/http/axiosAgentConfig';
import { validateCuratedResources } from '../client/src/api/curatedInspection';

export default async function curatedInspectionClients() {
  const endpoint = process.env.UNIFAI_TEST_UI_API_URL;
  const admin = process.env.UNIFAI_TEST_UI_ADMIN_COOKIE;
  const reader = process.env.UNIFAI_TEST_UI_OWNER_COOKIE;
  const rid = process.env.UNIFAI_TEST_UI_CURATED_RESOURCE;
  assert.ok(endpoint && admin && reader && rid);
  axios.defaults.baseURL = endpoint;
  axios.defaults.headers.common.Cookie = admin;
  const report = await validateCuratedResources([rid]);
  assert.equal(report.mode, 'curated_base');
  assert.ok(!Number.isNaN(Date.parse(report.observed_at)));
  assert.equal(report.results[0].is_valid, true);
  const owner = await axios.post('/resources/validation', { resource_ids: [rid] });
  assert.equal(owner.data[0].is_valid, false);
  axios.defaults.headers.common.Cookie = reader;
  await assert.rejects(validateCuratedResources([rid]), error =>
    !!error && typeof error === 'object' && 'response' in error &&
    (error.response as { status: number }).status === 403,
  );
  console.log('Curated inspection production clients passed');
}
