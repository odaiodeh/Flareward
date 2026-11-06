/** Canonical manual and Session clients approve and execute without receiving workflow tokens. */
import assert from 'node:assert/strict';
import axios from '../client/src/http/axiosAgentConfig';
import { inspectProgramExecution, startProgram, startProgramSessionTurn, type ProgramRef, type WorkflowAccess } from '../client/src/api/programs';
import { listReviews, respondToReview } from '../client/src/api/reviews';
import { workflowAccessCatalog } from '../client/src/api/workflow-access';

export default async function verifyWorkflowAccess() {
  const endpoint = process.env.UNIFAI_TEST_UI_API_URL;
  const human = process.env.UNIFAI_TEST_UI_HUMAN_COOKIE;
  const reviewer = process.env.UNIFAI_TEST_UI_REVIEW_COOKIE;
  const reference = process.env.UNIFAI_TEST_UI_PROGRAM_REFERENCE;
  assert.ok(endpoint && human && reviewer && reference);
  axios.defaults.baseURL = endpoint;
  axios.defaults.headers.common.Cookie = human;
  const catalog = await workflowAccessCatalog();
  assert.ok(catalog.some(item => item.purpose === 'review@1'));
  assert.equal(JSON.stringify(catalog).includes('root_execution_id'), false);
  const program: ProgramRef = JSON.parse(reference);
  const session = process.env.UNIFAI_TEST_UI_PROGRAM_SESSION;
  const root = session ? 'client-session-access' : 'client-manual-access';
  const access: WorkflowAccess = {
    purpose: 'review@1', scope: { policies: ['release@1'], actions: ['open', 'read', 'close'] },
    ttl_seconds: 60, renewable_for_seconds: 180,
  };
  const intent = { execution_id: root, inputs: { subject: { candidate: root } }, workflow_access: [access] };
  const started = session ? await startProgramSessionTurn(session, intent) : await startProgram({ ...intent, program });
  const approval = started.workflow_access_approval;
  assert.ok(approval);
  assert.equal(approval.root_execution_id, root);
  assert.equal(approval.approved_by.id, 'admission-owner');
  assert.match(approval.request_sha256, /^[a-f0-9]{64}$/);
  assert.deepEqual(approval.requirements, [access]);
  axios.defaults.headers.common.Cookie = reviewer;
  let inbox = await listReviews();
  const deadline = Date.now() + 20000;
  while (!inbox.reviews.some(review => review.root_execution_id === root) && Date.now() < deadline) {
    await new Promise(resolve => setTimeout(resolve, 50)); inbox = await listReviews();
  }
  const review = inbox.reviews.find(review => review.root_execution_id === root);
  assert.ok(review);
  await respondToReview(review.review_id, {
    key: 'client-admission-approval', expected_revision: review.revision, decision: 'approve',
    data: { feedback: 'Reviewed the exact client candidate' },
  });
  axios.defaults.headers.common.Cookie = human;
  let execution = await inspectProgramExecution(root);
  while (!['completed', 'failed', 'cancelled'].includes(execution.phase) && Date.now() < deadline) {
    await new Promise(resolve => setTimeout(resolve, 50)); execution = await inspectProgramExecution(root);
  }
  assert.equal(execution.phase, 'completed');
  assert.deepEqual(execution.workflow_access_approval, approval);
  const retried = session ? await startProgramSessionTurn(session, intent) : await startProgram({ ...intent, program });
  assert.deepEqual(retried.workflow_access_approval, approval);
  assert.equal(/unifai-review-v1\./.test(JSON.stringify([started, execution, retried])), false);
  console.log('Workflow access clients passed against native FastAPI');
}
