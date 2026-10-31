/** Real UI clients stream, approve, resume and cancel turns over HTTP; no model calls. */
import assert from 'node:assert/strict';
import { isAxiosError } from 'axios';
import axios from '../client/src/http/axiosAgentConfig';
import { saveBlueprint, deleteBlueprint } from '../client/src/api/blueprints';
import { createResource, deleteResource } from '../client/src/api/resources';
import {
  createSession, submitSession, getSessionStatus, getSessionChat, getSessionState,
  getSessionStreamStatus, subscribeToSessionStream, submitApproval, cancelSession,
  deleteSession, listSessions,
  getApprovalRules, submitApprovalRule,
} from '../client/src/api/sessions';
import { readSessionEvents } from '../client/src/api/session-stream';

const endpoint = process.env.UNIFAI_TEST_UI_API_URL;
assert.ok(endpoint, 'UNIFAI_TEST_UI_API_URL must identify an isolated native test API');
axios.defaults.baseURL = endpoint;

export default async function verifyChatClients() {
  const originalFetch = globalThis.fetch;
  globalThis.fetch = (input, init) => originalFetch(
    typeof input === 'string' && input.startsWith('/api2/') ? endpoint + input.slice('/api2'.length) : input,
    init,
  );
  let resourceId: string | undefined;
  let blueprintId: string | undefined;
  let sessionId: string | undefined;
  try {
    const node = await createResource({
      category: 'nodes', type: 'platform_approval', name: 'UI review fixture', config: {},
    });
    resourceId = node.rid;
    blueprintId = (await saveBlueprint(JSON.stringify({
      name: 'UI review workflow', nodes: [{ rid: `$ref:${node.rid}` }],
      plan: [{ uid: 'review', node: `$ref:${node.rid}` }],
    }))).blueprint_id;
    sessionId = await createSession({ blueprintId, hitlEnabled: true });
    const executionId = crypto.randomUUID();
    const request = { sessionId, executionId, inputs: { user_prompt: 'Please review' } };
    const submitted = await submitSession(request);
    assert.equal(submitted.executionId, executionId);
    assert.equal((await submitSession(request)).executionId, executionId);
    const controller = new AbortController();
    const response = await subscribeToSessionStream(sessionId, { executionId, signal: controller.signal });
    let sawApproval = false;
    for await (const event of readSessionEvents(response)) {
      if (event.type === 'approval_required') {
        assert.equal(event.root_execution_id, executionId);
        sawApproval = true;
        controller.abort();
        break;
      }
    }
    assert.equal(sawApproval, true);
    assert.equal(response.body?.locked, false);
    assert.equal((await getSessionStreamStatus(sessionId))?.is_active, true);
    // Detaching a reader does not cancel the application execution.
    assert.ok(['RUNNING', 'QUEUED'].includes(await getSessionStatus(sessionId)));
    await assert.rejects(
      submitApproval({ sessionId, requestId: 'probe-0', decision: 'approve' }),
      error => isAxiosError(error) && error.response?.status === 422,
    );
    const savedRule = await submitApprovalRule({
      sessionId, executionId, nodeUid: 'review', toolName: 'another-write', action: 'auto_approve',
    });
    assert.equal(savedRule.status, 'saved');
    assert.deepEqual((await getApprovalRules(sessionId)).overrides.node_rules.review.auto_approve_tools, ['another-write']);
    await submitApproval({ sessionId, executionId, requestId: 'probe-0', decision: 'approve' });
    assert.equal((await axios.get(`/executions/${executionId}/result`)).data.phase, 'completed');
    const chat = await getSessionChat(sessionId);
    assert.equal(chat.status, 'COMPLETED');
    assert.deepEqual(JSON.parse(chat.output).decisions, ['approve']);
    assert.equal(JSON.parse(chat.output).credential_user, 'owner');
    assert.deepEqual(await getSessionState(sessionId), { output: chat.output });
    const replay = [];
    for await (const event of readSessionEvents(await subscribeToSessionStream(sessionId, { executionId }))) replay.push(event);
    assert.equal(replay.at(-1)?.type, 'stream_end');
    assert.ok(replay.some(event => event.type === 'fixture_step'));
    const listed = await listSessions(new URLSearchParams({ limit: '1', offset: '0' }));
    assert.equal(listed.pagination.total, 1);
    assert.equal(listed.sessions[0].session_id, sessionId);
    const secondId = crypto.randomUUID();
    await submitSession({ sessionId, executionId: secondId, inputs: {} });
    await assert.rejects(subscribeToSessionStream(sessionId, { executionId }), {
      message: 'Stream subscription failed (HTTP 409)',
    });
    for await (const event of readSessionEvents(await subscribeToSessionStream(sessionId, { executionId: secondId }))) {
      assert.notEqual(event.execution_id, executionId);
      if (event.type === 'approval_required') {
        assert.equal(event.root_execution_id, secondId);
        assert.equal(event.request_id, 'probe-0');
        break;
      }
    }
    // Both turns reuse probe-0: an old card must not approve or edit the new turn.
    await assert.rejects(
      submitApproval({ sessionId, executionId, requestId: 'probe-0', decision: 'approve' }),
      error => isAxiosError(error) && error.response?.status === 409,
    );
    await assert.rejects(
      submitApprovalRule({ sessionId, executionId, action: 'auto_reject' }),
      error => isAxiosError(error) && error.response?.status === 409,
    );
    assert.deepEqual((await getApprovalRules(sessionId)).overrides.node_rules.review.auto_approve_tools, ['another-write']);
    await submitApprovalRule({ sessionId, executionId: secondId, action: 'clear' });
    assert.deepEqual((await getApprovalRules(sessionId)).overrides.node_rules, {});
    await cancelSession(sessionId);
    const terminal = (await axios.get(`/executions/${secondId}/result`)).data.phase;
    assert.ok(['cancelled', 'completed'].includes(terminal));
    assert.equal((await axios.get(`/executions/${executionId}/children`)).data.length, 0);
    await deleteSession(sessionId);
    sessionId = undefined;
    console.log('Existing UI session clients passed against native FastAPI');
  } finally {
    globalThis.fetch = originalFetch;
    if (sessionId) {
      await cancelSession(sessionId);
      const active = (await axios.get(`/sessions/${encodeURIComponent(sessionId)}`)).data.active_execution_id;
      if (active) await axios.get(`/executions/${encodeURIComponent(active)}/result`);
      await deleteSession(sessionId);
    }
    if (blueprintId) await deleteBlueprint(blueprintId);
    if (resourceId) await deleteResource(resourceId);
  }
}
