import React, { useState } from 'react';
import { useInfiniteQuery, useQueryClient } from '@tanstack/react-query';
import { executionReviews } from '@/api/reviews';
import { Button } from '@/components/ui/button';
import ReviewDetail from './ReviewDetail';

/** Root-scoped owner inspection shares the inbox's exact-occurrence decision form. */
export default function ExecutionReviews({ root, scope, teamId, human }: {
  root: string; scope: string; teamId?: string; human: string;
}) {
  const [selected, setSelected] = useState('');
  const cache = useQueryClient();
  const query = useInfiniteQuery({
    queryKey: ['execution-reviews', scope, root], initialPageParam: '',
    queryFn: ({ pageParam, signal }) => executionReviews(root, teamId, pageParam, signal),
    getNextPageParam: page => page.next_cursor ?? undefined,
    refetchInterval: 5000, retry: false,
  });
  const reviews = query.data?.pages.flatMap(page => page.reviews) ?? [];
  const current = reviews.find(review => review.review_id === selected) ?? reviews.find(review => review.status === 'pending') ?? reviews[0];
  return <section aria-label="Execution reviews" className="space-y-3"><h2 className="font-semibold">Human review</h2>
    {query.isPending && <p role="status">Loading execution reviews…</p>}
    {query.isError && <p role="alert">Review observation is unavailable. Previously observed reviews may be out of date.</p>}
    {!query.isPending && !query.isError && !reviews.length && <p className="text-sm text-muted-foreground">No reviews recorded for this execution.</p>}
    <nav aria-label="Reviews for this execution" className="flex flex-wrap gap-2">{reviews.map(review => <Button key={review.review_id} type="button" variant={current?.review_id === review.review_id ? 'default' : 'outline'} onClick={() => setSelected(review.review_id)}>{review.specification.prompt} · {review.status}</Button>)}</nav>
    {query.hasNextPage && <Button variant="outline" disabled={query.isFetchingNextPage} onClick={() => void query.fetchNextPage()}>Older execution reviews</Button>}
    {current && <ReviewDetail key={current.review_id} review={current} unavailable={query.isError} canRespond={current.reviewers.includes(human)} onUpdated={() => {
      void cache.invalidateQueries({ queryKey: ['execution-reviews', scope, root] });
      void cache.invalidateQueries({ queryKey: ['execution', scope] });
    }} />}
  </section>;
}
