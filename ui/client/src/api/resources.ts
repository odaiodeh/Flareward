import axios from '@/http/axiosAgentConfig';
import { ElementSchema, ResourceExecutionDefaults, ResourceKey, ResourceSourceRef } from '@/types/workspace';
import type { ResourceDefinition } from '@/api/programs';

export interface ElementBundle {
  schema_version: 2;
  root: ResourceKey;
  entries: { resource: ResourceDefinition; dependencies: ResourceKey[] }[];
  content_digest: string;
}

export async function captureResourceSnapshot(
  source: ResourceSourceRef, teamId?: string, signal?: AbortSignal,
): Promise<ElementBundle> {
  return (await axios.post<ElementBundle>('/resources/snapshot', { source }, {
    params: { teamId }, signal,
  })).data;
}

export interface ResourceIdentity {
  type: 'user' | 'team' | 'system';
  id: string;
  display_name: string;
}

export interface ResourceInstance {
  rid: string;
  identity: ResourceIdentity;
  category: string;
  type: string;
  name: string;
  version: number;
  cfg_dict: Record<string, unknown>;
  execution?: ResourceExecutionDefaults;
  nested_refs: string[];
  contributed_by?: string;
  created: string;
  updated: string;
  ownership?: 'builtin' | 'custom';
  visibility?: 'draft' | 'public';
  user_configured?: boolean;
  source?: ResourceSourceRef | null;
  /**
   * Present when toggling/promoting to "available to all" cascaded to
   * aggregated elements (LLMs, providers, tools, etc.) that weren't
   * already public built-ins — they were made available to all too.
   */
  cascaded_resources?: ResourceDependencySummary[];
}

/** Minimal info about a related resource surfaced on cascade/blocked responses. */
export interface ResourceDependencySummary {
  rid: string;
  name: string;
  category: string;
}

export interface ResourcesListResponse {
  resources: ResourceInstance[];
  pagination: {
    total: number;
    limit: number;
    offset: number;
    has_more: boolean;
  };
}

export interface ResourcePage {
  resources: ResourceInstance[]; total: number; offset: number; limit: number;
}

export async function listResourcePage(params: {
  category?: string; offset?: number; limit?: number; teamId?: string; signal?: AbortSignal;
}): Promise<ResourcePage> {
  const { signal, ...query } = params;
  return (await axios.get<ResourcePage>('/resources', { params: query, signal })).data;
}

export async function getResourceSnapshotSource(resourceId: string, teamId?: string, signal?: AbortSignal): Promise<ResourceInstance> {
  return (await axios.get<ResourceInstance>(`/resources/${encodeURIComponent(resourceId)}`, { params: { teamId }, signal })).data;
}

export interface BuiltinsListResponse {
  resources: ResourceInstance[];
}

export async function listResources(params: {
  signal?: AbortSignal;
  teamId?: string;
  category?: string;
  type?: string;
  ownership?: string;
  limit?: number;
  offset?: number;
}): Promise<ResourcesListResponse> {
  const query = new URLSearchParams();
  if (params.teamId) query.set('teamId', params.teamId);
  if (params.category) query.set('category', params.category);
  if (params.type) query.set('type', params.type);
  if (params.ownership) query.set('ownership', params.ownership);
  if (params.limit != null) query.set('limit', String(params.limit));
  if (params.offset != null) query.set('offset', String(params.offset));

  const { data } = await axios.get<ResourcesListResponse>(
    `/resources/resources.list?${query.toString()}`,
    { signal: params.signal },
  );
  return data;
}

/**
 * Fetch a caller's *complete* resource set for the given filters — pages
 * through with `offset`/`has_more` (server caps `limit` at 1000/request)
 * instead of assuming everything fits in one page. Use this whenever the
 * caller needs "all resources matching X" (dropdown/$ref sources, building
 * blocks, name lookups, etc.) rather than a UI-paginated list.
 */
export async function listAllResources(params: {
  signal?: AbortSignal;
  teamId?: string;
  category?: string;
  type?: string;
  ownership?: string;
}): Promise<ResourceInstance[]> {
  const PAGE_SIZE = 1000;
  const MAX_PAGES = 50;
  const resources: ResourceInstance[] = [];
  let offset = 0;
  let hasMore = true;
  let pages = 0;

  while (hasMore && pages < MAX_PAGES) {
    const page = await listResources({ ...params, limit: PAGE_SIZE, offset });
    resources.push(...page.resources);
    hasMore = !!page.pagination?.has_more && page.resources.length > 0;
    if (hasMore) offset += page.resources.length;
    pages++;
  }

  return resources;
}

export async function getResource(resourceId: string): Promise<ResourceInstance> {
  const { data } = await axios.get<ResourceInstance>(
    `/resources/resource.get?resourceId=${encodeURIComponent(resourceId)}`,
  );
  return data;
}

export async function createResource(payload: {
  teamId?: string;
  category: string;
  type: string;
  name: string;
  config: Record<string, any>;
  execution?: ResourceExecutionDefaults;
}): Promise<ResourceInstance> {
  const { data } = await axios.post<ResourceInstance>('/resources/resource.save', payload);
  return data;
}

export async function updateResource(payload: {
  resourceId: string;
  config: Record<string, any>;
  name?: string;
  teamId?: string;
  expected_version?: number;
  execution?: ResourceExecutionDefaults;
}): Promise<ResourceInstance> {
  const { data } = await axios.put<ResourceInstance>('/resources/resource.update', payload);
  return data;
}

export async function deleteResource(resourceId: string): Promise<void> {
  await axios.delete(`/resources/resource.delete?resourceId=${encodeURIComponent(resourceId)}`);
}

export async function getResourceSchema(signal?: AbortSignal): Promise<any> {
  const { data } = await axios.get('/resources/resource.schema', { signal });
  return data;
}

export async function validateResources(payload: {
  resourceIds: string[];
  userId?: string;
  timeoutSeconds?: number;
  maxWorkers?: number;
}): Promise<any[]> {
  const { data } = await axios.post('/resources/resources.validate', payload);
  return data;
}

export async function uploadResourceFile(
  file: File,
  format: string = "pem",
): Promise<{ content: string; filename: string; size_bytes: number; format_valid: boolean }> {
  const formData = new FormData();
  formData.append("file", file);
  formData.append("format", format);

  const response = await axios.post("/resources/resource.upload-file", formData, {
    headers: { "Content-Type": "multipart/form-data" },
  });
  return response.data;
}

// --- Built-in resource endpoints ---

export async function getBuiltinUserConfig(params: {
  resourceId: string;
  teamId?: string;
}): Promise<Record<string, any> | null> {
  const { data } = await axios.get<{ fields: Record<string, unknown> } | null>(
    `/resources/${encodeURIComponent(params.resourceId)}/configuration`,
    { params: params.teamId ? { teamId: params.teamId } : undefined },
  );
  return data?.fields ?? null;
}

export async function listBuiltins(params?: { category?: string; type?: string }): Promise<BuiltinsListResponse> {
  const resources: ResourceInstance[] = [];
  let offset = 0;
  while (true) {
    const { data } = await axios.get<ResourcePage>('/administration/resources', {
      params: { ...params, offset, limit: 100 },
    });
    resources.push(...data.resources);
    offset += data.resources.length;
    if (offset >= data.total) return { resources };
    if (!data.resources.length) throw new Error('Curated resource listing changed; refresh it');
  }
}

export async function getBuiltin(resourceId: string): Promise<ResourceInstance> {
  return (await axios.get<ResourceInstance>(`/administration/resources/${encodeURIComponent(resourceId)}`)).data;
}

export async function getBuiltinSchema(resourceId: string): Promise<ElementSchema['config_schema']> {
  return (await axios.get<ElementSchema['config_schema']>(`/resources/${encodeURIComponent(resourceId)}/configuration-schema`)).data;
}

export async function getElementSpec(category: string, type: string, signal?: AbortSignal): Promise<ElementSchema> {
  const { data } = await axios.get<ElementSchema>(
    `/catalog/element.spec.get?category=${encodeURIComponent(category)}&type=${encodeURIComponent(type)}`,
    { signal },
  );
  return data;
}

export async function configureBuiltin(payload: {
  resourceId: string; teamId?: string; config: Record<string, unknown>; expectedVersion?: number;
}): Promise<ResourceInstance> {
  await axios.patch(`/resources/${encodeURIComponent(payload.resourceId)}/configuration`, {
    config: payload.config, expected_version: payload.expectedVersion,
  }, { params: payload.teamId ? { teamId: payload.teamId } : undefined });
  return getResourceSnapshotSource(payload.resourceId, payload.teamId);
}

export async function createBuiltin(payload: {
  teamId?: string; category: string; type: string; name: string;
  config: Record<string, unknown>; availableToAll?: boolean;
  execution?: ResourceExecutionDefaults;
}): Promise<ResourceInstance> {
  const { teamId, availableToAll, ...resource } = payload;
  return (await axios.post<ResourceInstance>('/administration/resources', {
    ...resource, public: availableToAll ?? false,
  }, { params: teamId ? { teamId } : undefined })).data;
}

export async function updateBuiltin(payload: {
  resourceId: string; expectedVersion: number; config?: Record<string, unknown>;
  name?: string; availableToAll?: boolean;
  execution?: ResourceExecutionDefaults;
}): Promise<ResourceInstance> {
  const { resourceId, expectedVersion, availableToAll, ...changes } = payload;
  return (await axios.put<ResourceInstance>(`/administration/resources/${encodeURIComponent(resourceId)}`, {
    ...changes, expected_version: expectedVersion, public: availableToAll,
  })).data;
}

export async function toggleBuiltinVisibility(payload: {
  resourceId: string; expectedVersion: number; availableToAll: boolean;
}): Promise<ResourceInstance> {
  return updateBuiltin(payload);
}

export async function deleteBuiltin(resourceId: string, expectedVersion: number): Promise<void> {
  await axios.delete(`/administration/resources/${encodeURIComponent(resourceId)}`, {
    params: { expected_version: expectedVersion },
  });
}

/** Preview the dependency resources that publication would make public. */
export async function previewBuiltinCascade(resourceId: string): Promise<ResourceDependencySummary[]> {
  return (await axios.get<ResourceDependencySummary[]>(
    `/administration/resources/${encodeURIComponent(resourceId)}/publication-preview`,
  )).data;
}

// --- Admin edit lock endpoints (built-in resources) ---

export interface BuiltinEditLockHolder {
  userId: string;
  displayName: string;
}

export async function acquireBuiltinEditLock(entityId: string): Promise<
  { acquired: true } | { acquired: false; lockedBy: BuiltinEditLockHolder }
> {
  const { data } = await axios.post<{ acquired: boolean; lockedBy?: BuiltinEditLockHolder }>(
    `/administration/resources/${encodeURIComponent(entityId)}/edit-lease`,
  );
  if (data.acquired) return { acquired: true };
  return { acquired: false, lockedBy: data.lockedBy ?? { userId: '?', displayName: 'Another admin' } };
}

export async function releaseBuiltinEditLock(entityId: string): Promise<void> {
  await axios.delete(`/administration/resources/${encodeURIComponent(entityId)}/edit-lease`);
}

export async function heartbeatBuiltinEditLock(entityId: string): Promise<void> {
  const { data } = await axios.put<{ renewed: boolean }>(
    `/administration/resources/${encodeURIComponent(entityId)}/edit-lease`,
  );
  if (!data.renewed) throw new Error('Editing lease expired; reload before saving');
}
