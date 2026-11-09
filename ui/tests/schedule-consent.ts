/** Canonical schedule clients inspect/revoke durable consent without receiving tokens. */
import assert from 'node:assert/strict';
import axios from '../client/src/http/axiosAgentConfig';
import { createProgramSchedule, deleteProgramSchedule, getProgramSchedule, listProgramSchedules, revokeProgramScheduleAccess, type CreateProgramSchedule } from '../client/src/api/program-schedules';
import type { ProgramRef } from '../client/src/api/programs';

export default async function verifyScheduleConsent() {
  const endpoint = process.env.FLAREWARD_TEST_UI_API_URL;
  const cookie = process.env.FLAREWARD_TEST_UI_HUMAN_COOKIE;
  const reference = process.env.FLAREWARD_TEST_UI_PROGRAM_REFERENCE;
  const key = process.env.FLAREWARD_TEST_UI_SCHEDULE_KEY;
  assert.ok(endpoint && cookie && reference && key);
  axios.defaults.baseURL = endpoint; axios.defaults.headers.common.Cookie = cookie;
  const program: ProgramRef = JSON.parse(reference);
  const request: CreateProgramSchedule = {
    session: { program }, inputs: { subject: { candidate: 'client-scheduled-candidate' } },
    schedule: { interval: 'P1D', enabled: false },
    workflow_access: {
      requirements: [{ purpose: 'review@1', scope: { policies: ['release@1'], actions: ['open', 'read', 'close'] }, ttl_seconds: 60 }],
      expires_at: new Date(Date.now() + 3600000).toISOString(),
    },
  };
  const created = await createProgramSchedule(request, key);
  const id = created.definition.schedule_id;
  try {
    assert.equal(created.status, 'paused');
    assert.equal(created.workflow_access_consent?.approved_by.id, 'admission-owner');
    assert.equal(created.authorization_id, created.workflow_access_consent?.consent_id);
    assert.equal(created.workflow_access_consent?.revoked, false);
    assert.deepEqual((await getProgramSchedule(id)).workflow_access_consent, created.workflow_access_consent);
    assert.deepEqual((await listProgramSchedules()).find(value => value.definition.schedule_id === id)?.workflow_access_consent, created.workflow_access_consent);
    await revokeProgramScheduleAccess(id);
    const revoked = await getProgramSchedule(id);
    assert.equal(revoked.workflow_access_consent?.revoked, true);
    assert.equal((await listProgramSchedules()).find(value => value.definition.schedule_id === id)?.workflow_access_consent?.revoked, true);
    const retried = await createProgramSchedule(request, key);
    assert.equal(retried.authorization_id, created.authorization_id);
    assert.equal(retried.workflow_access_consent?.revoked, true);
    assert.equal(/flareward-review-v1\./.test(JSON.stringify([created, revoked, retried])), false);
  } finally {
    await deleteProgramSchedule(id);
  }
  console.log('Schedule consent clients passed against native FastAPI');
}
