import platformApi from '@/http/axiosAgentConfig';

// ─────────────────────────────────────────────────────────────────────────────
//  Types
// ─────────────────────────────────────────────────────────────────────────────

export interface FieldValue {
  key: string;
  label: string;
  field_type: string;
  description: string;
  default: unknown;
  placeholder: string;
  value: unknown;
}

export interface SectionValue {
  key: string;
  title: string;
  description: string;
  fields: FieldValue[];
  on_update_action: string | null;
  updated_at: string | null;
  revision: number;
}

export interface CategoryValue {
  key: string;
  title: string;
  description: string;
  sections: SectionValue[];
}

export interface AdminConfigResponse {
  categories: CategoryValue[];
}

export interface UpdateSectionResponse {
  status: string;
  on_update_action: string | null;
}

// ─────────────────────────────────────────────────────────────────────────────
//  API calls
// ─────────────────────────────────────────────────────────────────────────────

/**
 * Fetch the full admin config template merged with stored values.
 * Session cookie provides authentication automatically.
 */
export async function getAdminConfig(): Promise<AdminConfigResponse> {
  const response = await platformApi.get('/administration/configuration');
  return response.data;
}

/**
 * Update a single config section's values.
 * Session cookie provides authentication automatically.
 */
export async function updateAdminConfigSection(
  sectionKey: string,
  values: Record<string, unknown>,
  expectedRevision: number,
): Promise<UpdateSectionResponse> {
  const response = await platformApi.put(
    '/administration/configuration',
    { section: sectionKey, values, expected_revision: expectedRevision },
  );
  return response.data;
}

/**
 * Check whether the authenticated human has administrator access.
 */
export async function checkAdminAccess(): Promise<{ is_admin: boolean }> {
  const response = await platformApi.get('/administration/access');
  return response.data;
}
