import React, { useEffect, useRef, useState } from 'react';
import { Link } from 'wouter';
import axios from 'axios';
import type { JsonValue } from '@shared/json';
import { respondToReview, type ReviewDecision, type ReviewRecord, type ReviewSubmission } from '@/api/reviews';
import SchemaValue from '@/components/schema/SchemaValue';
import { initialSchemaInput } from '@/components/schema/schema';
import ArtifactReferences from '@/components/artifacts/ArtifactReferences';
import { useWorkspaceIdentity } from '@/hooks/use-workspace-identity';

function message(error: unknown): string {
  if (axios.isAxiosError(error) && typeof error.response?.data?.detail === 'string') return error.response.data.detail;
  return 'Unable to confirm the review state. Refresh or retry the same decision.';
}

export default function ReviewDetail({ review, unavailable, onUpdated, canRespond = true }: { review: ReviewRecord; unavailable: boolean; onUpdated: (review: ReviewRecord) => void; canRespond?: boolean }) {
  const owner = useWorkspaceIdentity();
  const scope = JSON.stringify([owner.isTeam, owner.userId, owner.credentialUserId]);
  const [data, setData] = useState<JsonValue>(() => initialSchemaInput(review.specification.response_schema));
  const [attempt, setAttempt] = useState<ReviewSubmission | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const request = useRef<AbortController | null>(null);
  useEffect(() => () => { request.current?.abort(); }, []);

  const submit = async (decision: ReviewDecision) => {
    if (request.current || unavailable) return;
    let submission = attempt;
    if (!submission) {
      submission = { key: crypto.randomUUID(), expected_revision: review.revision, decision, data: structuredClone(data) };
    }
    const controller = new AbortController();
    request.current = controller;
    setAttempt(submission);
    setBusy(true);
    setError('');
    try {
      const accepted = await respondToReview(review.review_id, submission, controller.signal);
      if (!controller.signal.aborted) onUpdated(accepted);
    } catch (failure) {
      if (!controller.signal.aborted) {
        setError(message(failure));
        // A definite client rejection permits correction. An uncertain delivery reuses the exact intent.
        if (axios.isAxiosError(failure) && failure.response && failure.response.status >= 400 && failure.response.status < 500) setAttempt(null);
      }
    } finally {
      if (!controller.signal.aborted) { request.current = null; setBusy(false); }
    }
  };

  return <section aria-label="Review details" className="min-w-0 space-y-5 rounded-lg border p-5">
    <div><h2 className="text-xl font-semibold whitespace-pre-wrap">{review.specification.prompt}</h2>
      <p className="mt-2 text-sm text-muted-foreground">{review.owner.type}: {review.owner.id} · {review.status}</p>
      <p className="text-sm">Expires {new Date(review.expires_at).toLocaleString()}</p></div>
    <details><summary>Execution and policy</summary><dl className="break-all text-sm">
      <dt>Root execution</dt><dd><Link className="underline" href={`/executions/${encodeURIComponent(review.root_execution_id)}`}>{review.root_execution_id}</Link></dd><dt>Review execution</dt><dd>{review.execution_id}</dd>
      <dt>Policy</dt><dd>{review.policy}</dd><dt>Review</dt><dd>{review.review_id}</dd>
    </dl></details>
    <div><h3 className="font-medium">Subject</h3><pre className="max-h-72 overflow-auto whitespace-pre-wrap break-words rounded bg-muted p-3 text-sm">{JSON.stringify(review.specification.subject, null, 2)}</pre></div>
    <ArtifactReferences values={[review.specification.subject]} scope={scope} teamId={owner.teamId} />
    {review.status === 'pending' && !canRespond ? <p role="status">Waiting for an assigned reviewer.</p> : review.status === 'pending' ? <form onSubmit={event => {
      event.preventDefault();
      const button = (event.nativeEvent as SubmitEvent).submitter as HTMLButtonElement | null;
      const decision = attempt?.decision ?? button?.value;
      if (decision === 'approve' || decision === 'reject') void submit(decision);
    }} className="space-y-4">
      <SchemaValue schema={review.specification.response_schema} label="Review response" value={data} onChange={value => setData(value ?? null)} disabled={unavailable || busy || attempt !== null} />
      {error && <p role="alert" className="text-red-500">{error}</p>}
      {attempt && !busy && <p className="text-sm">Delivery is unconfirmed. Retry sends the same decision and response.</p>}
      <div className="flex gap-3">{(attempt ? [attempt.decision] : review.specification.decisions).map(decision => <button
        key={decision} type="submit" value={decision} disabled={busy || unavailable} className="rounded border px-4 py-2 disabled:opacity-50">
        {busy ? 'Submitting…' : attempt ? `Retry ${decision}` : decision === 'approve' ? 'Approve' : 'Reject'}
      </button>)}</div>
    </form> : <div role="status" className="space-y-2">
      {review.response ? <><p className="font-semibold">{review.response.decision === 'approve' ? 'Approved' : 'Rejected'} by {review.response.issued_by.id}</p>
        <p className="text-sm">{new Date(review.response.recorded_at).toLocaleString()}</p>
        <pre className="overflow-auto whitespace-pre-wrap text-sm">{JSON.stringify(review.response.data, null, 2)}</pre></> : <p>This review is {review.status}.</p>}
      {review.superseded_by && <a className="underline" href={`/reviews/${review.superseded_by}`}>View replacement review</a>}
      {review.delivery_pending && <p className="text-sm">The decision is saved; workflow notification is pending.</p>}
    </div>}
  </section>;
}

