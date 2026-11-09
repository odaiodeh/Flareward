/** Production notification clients against actual native HTTP and seeded Mongo invitations. */
import assert from 'node:assert/strict';
import axios from '../client/src/http/axiosAgentConfig';
import { declineShare, formatShareSenderLabel, getShare, listShares } from '../client/src/api/shares';

const endpoint = process.env.FLAREWARD_TEST_UI_API_URL;
assert.ok(endpoint);
axios.defaults.baseURL = endpoint;

export default async function verifyNotifications() {
  const received = await listShares('received', 'pending');
  assert.equal(received.count, 1);
  assert.equal(received.invites[0].share_id, 'ui-received');
  assert.equal(formatShareSenderLabel(received.invites[0]), 'Fixture sender');
  assert.ok(!JSON.stringify(received).includes('internal-owner-pool'));
  assert.deepEqual((await listShares('sent')).invites.map(invite => invite.share_id), ['ui-sent']);
  assert.equal((await listShares('received', undefined, 1, 1)).count, 0);
  const before = await getShare('ui-received');
  assert.equal(before.recipient_user_id, 'owner');
  assert.equal((await declineShare({ shareId: before.share_id })).status, 'success');
  assert.equal((await declineShare({ shareId: before.share_id })).status, 'success');
  const after = await getShare(before.share_id);
  assert.equal(after.status, 'declined');
  assert.ok(after.declined_at);
  assert.equal((await listShares('received', 'pending')).count, 0);
  await assert.rejects(getShare('ui-foreign'), error => !!error && typeof error === 'object' && 'response' in error && (error.response as {status: number}).status === 403);
  await assert.rejects(declineShare({ shareId: 'ui-sent' }), error => !!error && typeof error === 'object' && 'response' in error && (error.response as {status: number}).status === 403);
  const controller = new AbortController();
  controller.abort();
  await assert.rejects(listShares('received', undefined, 0, 100, undefined, controller.signal));
  console.log('Existing UI sharing notification clients passed against native FastAPI');
}
