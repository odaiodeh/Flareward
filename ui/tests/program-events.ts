/** Delivery credentials trigger pinned work; the human uses the existing execution client. */
import assert from 'node:assert/strict';
import { isAxiosError } from 'axios';
import axios from '../client/src/http/axiosAgentConfig';
import { createProgramEventSource, deliverProgramEvent, getProgramEventSource, getProgramEventSourceSettings, listProgramEventSources, revokeProgramEventSource, rotateProgramEventCredential } from '../client/src/api/program-events';
import { inspectProgramExecution, type ProgramRef } from '../client/src/api/programs';

export default async function verifyProgramEvents() {
  const endpoint = process.env.LUMORA_TEST_UI_API_URL;
  const cookie = process.env.LUMORA_TEST_UI_HUMAN_COOKIE;
  const reference = process.env.LUMORA_TEST_UI_PROGRAM_REFERENCE;
  assert.ok(endpoint && cookie && reference);
  axios.defaults.baseURL = endpoint; axios.defaults.headers.common.Cookie = cookie;
  const program: ProgramRef = JSON.parse(reference);
  const created = await createProgramEventSource({
    name: 'Client event source', program, event_type: 'issue@1',
    expires_at: new Date(Date.now() + 3600000).toISOString(),
    input_schema: { type: 'object', required: ['name'], properties: { name: { type: 'string' } }, additionalProperties: false },
  });
  const id = created.source.source_id;
  try {
    assert.equal(created.source.approved_by.id, 'admission-owner');
    assert.deepEqual(await getProgramEventSource(id), created.source);
    const settings = await getProgramEventSourceSettings(id);
    assert.ok(settings.admitted_profiles?.profiles.includes(settings.admitted_profiles.default_profile));
    assert.deepEqual(settings.placement?.program, program);
    assert.equal(settings.placement?.dynamic_invocations, true);
    assert.deepEqual((await listProgramEventSources()).find(value => value.source_id === id), created.source);
    const event = { event_id: 'issue-42', event_type: 'issue@1', inputs: { name: 'client event' } };
    const receipts = await Promise.all(Array.from({ length: 5 }, () => deliverProgramEvent(created.credential, event)));
    assert.equal(new Set(receipts.map(value => value.execution_id)).size, 1);
    assert.equal(Object.hasOwn(receipts[0], 'result'), false);
    assert.equal(Object.hasOwn(receipts[0], 'context'), false);
    const execution = receipts[0].execution_id;
    const deadline = Date.now() + 20000;
    let observed = await inspectProgramExecution(execution);
    while (!['completed', 'failed', 'cancelled'].includes(observed.phase) && Date.now() < deadline) {
      await new Promise(resolve => setTimeout(resolve, 20));
      observed = await inspectProgramExecution(execution);
    }
    assert.equal(observed.phase, 'completed');
    assert.deepEqual(observed.result, { answer: 'hello client event' });
    assert.deepEqual(observed.program, program);
    assert.deepEqual(observed.admitted_profiles, settings.admitted_profiles);
    assert.deepEqual(observed.work_limits, settings.work_limits);
    const rotated = await rotateProgramEventCredential(id, settings.credential_revision);
    assert.equal(rotated.revision, settings.credential_revision + 1);
    assert.equal((await getProgramEventSourceSettings(id)).credential_revision, rotated.revision);
    await assert.rejects(deliverProgramEvent(created.credential, event), error => isAxiosError(error) && error.response?.status === 401);
    assert.equal((await deliverProgramEvent(rotated.credential, event)).execution_id, execution);
    await assert.rejects(rotateProgramEventCredential(id, settings.credential_revision), error => isAxiosError(error) && error.response?.status === 409);
    await assert.rejects(deliverProgramEvent(rotated.credential, { ...event, inputs: { name: 'changed event' } }), error => isAxiosError(error) && error.response?.status === 409);
    await revokeProgramEventSource(id);
    assert.equal((await getProgramEventSource(id)).revoked, true);
    await assert.rejects(deliverProgramEvent(rotated.credential, event), error => isAxiosError(error) && error.response?.status === 401);
    assert.equal(JSON.stringify([observed, ...receipts]).includes(created.credential), false);
  } finally {
    await revokeProgramEventSource(id);
  }
  console.log('Program event clients passed against native FastAPI');
}
