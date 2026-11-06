/** Production reviewer clients use a real assigned session and native workflow occurrence. */
import assert from 'node:assert/strict';
import axios from '../client/src/http/axiosAgentConfig';
import { executionReviews, getReview, listReviews, respondToReview } from '../client/src/api/reviews';

export default async function verifyReviews() {
  const endpoint = process.env.UNIFAI_TEST_UI_API_URL;
  const cookie = process.env.UNIFAI_TEST_UI_REVIEW_COOKIE;
  assert.ok(endpoint && cookie);
  axios.defaults.baseURL = endpoint;
  axios.defaults.headers.common.Cookie = cookie;
  const inbox = await listReviews();
  assert.equal(inbox.reviews.length, 1);
  const review = await getReview(inbox.reviews[0].review_id);
  const ownerCookie = process.env.UNIFAI_TEST_UI_HUMAN_COOKIE;
  assert.ok(ownerCookie);
  assert.deepEqual((await executionReviews(review.root_execution_id)).reviews, []);
  axios.defaults.headers.common.Cookie = ownerCookie;
  const owned = await executionReviews(review.root_execution_id);
  assert.deepEqual(owned.reviews.map(value => value.review_id), [review.review_id]);
  assert.deepEqual((await executionReviews(review.root_execution_id, undefined, review.review_id)).reviews, []);
  assert.deepEqual((await executionReviews('different-root')).reviews, []);
  axios.defaults.headers.common.Cookie = cookie;
  assert.equal(review.status, 'pending');
  const submission = { key: 'ui-client-decision', expected_revision: review.revision, decision: 'reject' as const, data: { feedback: 'Request changes from the actual client' } };
  const accepted = await respondToReview(review.review_id, submission);
  assert.equal(accepted.status, 'decided');
  assert.equal(accepted.response?.issued_by.id, 'reviewer');
  assert.deepEqual((await respondToReview(review.review_id, submission)).response, accepted.response);
  assert.deepEqual((await getReview(review.review_id)).response, accepted.response);
  await assert.rejects(respondToReview(review.review_id, { ...submission, decision: 'approve' }), error =>
    !!error && typeof error === 'object' && 'response' in error && (error.response as { status: number }).status === 409);
  const controller = new AbortController(); controller.abort();
  await assert.rejects(listReviews(controller.signal));
  console.log('Human Review clients passed against native FastAPI');
}
