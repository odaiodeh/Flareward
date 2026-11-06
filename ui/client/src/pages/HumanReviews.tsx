import React, { useEffect, useState } from 'react';
import { useRoute } from 'wouter';
import axios from 'axios';
import { getReview, listReviews, type ReviewRecord } from '@/api/reviews';
import ReviewDetail from '@/components/reviews/ReviewDetail';

function message(error: unknown): string {
  if (axios.isAxiosError(error) && typeof error.response?.data?.detail === 'string') return error.response.data.detail;
  return 'Unable to confirm the review state. Refresh or retry the same decision.';
}

export default function HumanReviews() {
  const [, params] = useRoute('/reviews/:reviewId');
  const [reviews, setReviews] = useState<ReviewRecord[]>([]);
  const [selected, setSelected] = useState(params?.reviewId ?? '');
  const [detail, setDetail] = useState<ReviewRecord | null>(null);
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(true);
  const [refresh, setRefresh] = useState(0);
  const [cursor, setCursor] = useState<string | null>(null);
  const [after, setAfter] = useState('');
  useEffect(() => { if (params?.reviewId) setSelected(params.reviewId); }, [params?.reviewId]);
  useEffect(() => {
    const controller = new AbortController();
    let timer: ReturnType<typeof setTimeout> | undefined;
    const load = async () => {
      try {
        const page = await listReviews(controller.signal, after);
        const current = selected ? await getReview(selected, controller.signal) : null;
        if (controller.signal.aborted) return;
        setReviews(previous => page.reviews.map(value => {
          const known = previous.find(item => item.review_id === value.review_id);
          return known && known.revision > value.revision ? known : value;
        }));
        setCursor(page.next_cursor);
        setDetail(previous => current && previous?.review_id === current.review_id && previous.revision > current.revision ? previous : current);
        setError('');
      } catch (failure) {
        if (!controller.signal.aborted) setError(message(failure));
      } finally {
        if (!controller.signal.aborted) { setLoading(false); timer = setTimeout(() => { void load(); }, 5000); }
      }
    };
    setLoading(true);
    void load();
    return () => { controller.abort(); clearTimeout(timer); };
  }, [selected, after, refresh]);

  return <main className="h-full overflow-auto p-6 space-y-5">
    <div className="flex justify-between gap-4"><div><h1 className="text-2xl font-semibold">Human Reviews</h1>
      <p className="text-muted-foreground">Reviews assigned to you, including work owned by other users or teams.</p></div>
      <button className="rounded border px-3 py-2" onClick={() => setRefresh(value => value + 1)}>Refresh status</button></div>
    {error && <p role="alert" className="text-red-500">{error}</p>}
    {loading && <p role="status">Loading reviews…</p>}
    <div className="grid gap-5 lg:grid-cols-[minmax(220px,1fr)_2fr]">
      <nav aria-label="Assigned reviews" className="space-y-2">
        {!loading && !reviews.length && <p>No assigned reviews on this page.</p>}
        {reviews.map(review => <button key={review.review_id} aria-pressed={selected === review.review_id}
          className="w-full rounded border p-3 text-left aria-pressed:border-primary" onClick={() => setSelected(review.review_id)}>
          <span className="block font-medium truncate">{review.specification.prompt}</span>
          <span className="block text-sm">{review.owner.id} · {review.status}</span>
        </button>)}
        <div className="flex gap-3">{after && <button className="underline" onClick={() => setAfter('')}>Newest</button>}
          {cursor && <button className="underline" onClick={() => setAfter(cursor)}>Older reviews</button>}</div>
      </nav>
      {detail && detail.review_id === selected && <ReviewDetail key={detail.review_id} review={detail} unavailable={loading || !!error} onUpdated={updated => {
        setDetail(updated); setReviews(values => values.map(value => value.review_id === updated.review_id ? updated : value));
      }} />}
    </div>
  </main>;
}
