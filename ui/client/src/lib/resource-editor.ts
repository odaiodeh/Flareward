import type { ResourceInstance } from '@/api/resources';
import type { ElementInstance, ElementSchema } from '@/types/workspace';

export function toElementInstance(resource: ResourceInstance): ElementInstance {
  return {
    rid: resource.rid,
    name: resource.name,
    config: resource.cfg_dict,
    execution: resource.execution,
    category: resource.category,
    type: resource.type,
    version: resource.version,
    created: resource.created,
    updated: resource.updated,
    nested_refs: resource.nested_refs,
    contributed_by: resource.contributed_by,
    ownership: resource.ownership || 'custom',
    visibility: resource.visibility,
    userConfigured: resource.user_configured ?? false,
  };
}

/** The generic config form edits only the resource name and element config. */
export function elementFormSchema(
  element: ElementSchema,
  resource: { properties?: Record<string, unknown>; required?: string[] },
): ElementSchema {
  return {
    ...element,
    config_schema: {
      ...element.config_schema,
      properties: { name: resource.properties?.name, ...element.config_schema.properties },
      required: [...new Set([
        ...(resource.required?.includes('name') ? ['name'] : []),
        ...(element.config_schema.required ?? []),
      ])],
    },
  };
}
