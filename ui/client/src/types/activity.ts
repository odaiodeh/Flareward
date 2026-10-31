/** UI activity values produced by the data-source HTTP adapter. */
export interface ActivityItem {
  id: string;
  type: 'slack' | 'document';
  title: string;
  description: string;
  status: 'complete';
  source: string;
  destination: string;
  metadata: Record<string, unknown>;
  timestamp: string;
}
