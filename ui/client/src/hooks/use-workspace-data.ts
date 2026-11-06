import { useState, useEffect, useCallback, useMemo } from "react";
import { useInfiniteQuery, useQueryClient } from "@tanstack/react-query";
import axios from "../http/axiosAgentConfig";
import {
  ElementCategory,
  ElementType,
  ElementInstance,
  ElementSchema,
  CatalogResponse,
} from "../types/workspace";
import { useToast } from "./use-toast";
import { catalogService } from "@/api/catalog";
import * as resourcesApi from "@/api/resources";
import { useAgenticAI } from "@/contexts/AgenticAIContext";
import { useWorkspaceIdentity } from "@/hooks/use-workspace-identity";
import type { ResourceInstance } from "@/api/resources";
import { elementFormSchema, toElementInstance } from "@/lib/resource-editor";
import { useLatestRequest } from './use-latest-request';

const INSTANCES_PAGE_SIZE = 50;

/**
 * When a resource is made available to all, any aggregated elements it
 * references (LLMs, providers, tools, etc.) that weren't already public
 * built-ins get swept along automatically. Builds the disclaimer text for
 * the success toast when that happened.
 */
function describeCascadedResources(result: ResourceInstance | null): string | null {
  const cascaded = result?.cascaded_resources;
  if (!cascaded || cascaded.length === 0) return null;
  const names = cascaded.map((r) => `"${r.name}"`).join(", ");
  return `Also made available to all, since this resource uses ${names}.`;
}

export const useWorkspaceData = () => {
  const [categories, setCategories] = useState<ElementCategory[]>([]);
  const [elementInstances, setElementInstances] = useState<ElementInstance[]>(
    [],
  );
  const [elementSchema, setElementSchema] = useState<ElementSchema | null>(
    null,
  );
  const [elementActions, setElementActions] = useState<any[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [isLoadingSchema, setIsLoadingSchema] = useState(false);
  const [isLoadingActions, setIsLoadingActions] = useState(false);
  const [isLoadingInstances, setIsLoadingInstances] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const { toast } = useToast();
  const { addOrUpdateResource, removeResource, revalidateResourceAndAncestors } = useAgenticAI();
  const { userId: USER_ID, teamId } = useWorkspaceIdentity();
  const beginInstances = useLatestRequest();
  const beginSchema = useLatestRequest();
  const beginActions = useLatestRequest();

  // Fetch all available categories and element types
  const fetchCategories = useCallback(async () => {
    try {
      setIsLoading(true);
      setError(null);
      const catalogData = await catalogService.fetchAllElements();

      const categoryList: ElementCategory[] = Object.entries(
        catalogData.elements,
      ).map(([category, elements]) => ({
        category,
        // Filter out elements with hints array containing hint_type === "hidden"
        elements: (elements || []).filter((element: ElementType) => 
          !element.hints?.some(hint => hint.hint_type === "hidden")
        ),
      }))
      // Filter out categories that have no visible elements after filtering
      .filter(category => category.elements.length > 0);

      setCategories(categoryList);
      return categoryList;
    } catch (err: any) {
      const errorMessage =
        err.response?.data?.error || "Failed to fetch categories";
      setError(errorMessage);
      toast({
        title: "Error",
        description: errorMessage,
        variant: "destructive",
      });
      console.error("Error fetching categories:", err);
      return null;
    } finally {
      setIsLoading(false);
    }
  }, [toast]);

  // Fetch element instances for a specific category and type using Resources API
  const fetchElementInstances = useCallback(
    async (category: string, type: string) => {
      const signal = beginInstances();
      try {
        setIsLoadingInstances(true);
        setError(null);
        setElementInstances([]);

        const resources = await resourcesApi.listAllResources({
          signal,
          teamId,
          category,
          type,
        });

        if (signal.aborted) return null;
        const instances = resources.map(toElementInstance);

        setElementInstances(instances);
        return instances;
      } catch (err: any) {
        if (signal.aborted) return null;
        const errorMessage =
          err.response?.data?.error || "Failed to fetch element instances";
        setError(errorMessage);
        toast({
          title: "Error",
          description: errorMessage,
          variant: "destructive",
        });
        console.error("Error fetching element instances:", err);
        setElementInstances([]);
        return null;
      } finally {
        if (!signal.aborted) setIsLoadingInstances(false);
      }
    },
    [toast, teamId, beginInstances],
  );

  // Fetch single resource by ID
  const fetchResourceById = useCallback(
    async (resourceId: string) => {
      try {
        setIsLoading(true);
        setError(null);

        return await resourcesApi.getResource(resourceId);
      } catch (err: any) {
        const errorMessage =
          err.response?.data?.error || "Failed to fetch resource";
        setError(errorMessage);
        toast({
          title: "Error",
          description: errorMessage,
          variant: "destructive",
        });
        console.error("Error fetching resource:", err);
        return null;
      } finally {
        setIsLoading(false);
      }
    },
    [toast],
  );

  // Fetch all resources for a category (for $ref dropdowns)
  const fetchResourcesForCategory = useCallback(
    async (category: string, ownership?: string) => {
      try {
        const resources = await resourcesApi.listAllResources({
          teamId,
          category,
          ownership,
        });

        return resources.map((resource) => ({
          rid: resource.rid,
          name: resource.name,
          type: resource.type,
          config: resource.cfg_dict,
          ownership: resource.ownership || 'custom',
          visibility: resource.visibility,
        }));
      } catch (err: any) {
        const errorMessage =
          err.response?.data?.error ||
          `Failed to fetch resources for category ${category}`;
        toast({
          title: "Error",
          description: errorMessage,
          variant: "destructive",
        });
        console.error("Error fetching resources for category:", err);
        return [];
      }
    },
    [toast, teamId],
  );

  // Fetch element schema for form generation (combines resource schema + element-specific schema)
  const fetchElementSchema = useCallback(
    async (category: string, type: string) => {
      const signal = beginSchema();
      try {
        setIsLoadingSchema(true);
        setElementSchema(null);
        setError(null);

        const [resourceSchema, elementSchema] = await Promise.all([
          resourcesApi.getResourceSchema(signal),
          resourcesApi.getElementSpec(category, type, signal),
        ]);
        if (signal.aborted) return null;

        const combinedSchema = elementFormSchema(elementSchema, resourceSchema);

        setElementSchema(combinedSchema);
        return combinedSchema;
      } catch (err: any) {
        if (signal.aborted) return null;
        const errorMessage =
          err.response?.data?.error || "Failed to fetch element schema";
        setError(errorMessage);
        toast({
          title: "Error",
          description: errorMessage,
          variant: "destructive",
        });
        console.error("Error fetching element schema:", err);
        setElementSchema(null);
        return null;
      } finally {
        if (!signal.aborted) setIsLoadingSchema(false);
      }
    },
    [toast, beginSchema],
  );

  // Fetch available actions for a given element category and type
  const fetchElementActions = useCallback(
    async (category: string, type: string) => {
      const signal = beginActions();
      try {
        setIsLoadingActions(true);
        setElementActions([]);
        setError(null);

        const response = await axios.get<any>('/actions/actions.list', {
          params: { category, type }, signal,
        });
        if (signal.aborted) return [];

        setElementActions(response.data.actions || []);
        return response.data.actions || [];
      } catch (err: any) {
        if (signal.aborted) return [];
        const errorMessage =
          err.response?.data?.error || "Failed to fetch element actions";
        setError(errorMessage);
        toast({
          title: "Error",
          description: errorMessage,
          variant: "destructive",
        });
        console.error("Error fetching element actions:", err);
        setElementActions([]);
        return [];
      } finally {
        if (!signal.aborted) setIsLoadingActions(false);
      }
    },
    [toast, beginActions],
  );

  // Save element (create or update) using Resources API
  const saveElement = useCallback(
    async (category: string, type: string, elementData: any, rid?: string) => {
      try {
        setIsLoading(true);
        setError(null);

        if (rid) {
          const result = await resourcesApi.updateResource({
            resourceId: rid,
            config: elementData.cfg_dict,
            name: elementData.name,
            teamId,
            execution: elementData.execution,
            expected_version: elementData.expected_version,
          });

          if (result) {
            addOrUpdateResource({
              rid: result.rid || rid,
              name: result.name || elementData.name,
              category: result.category || category,
              type: result.type || type,
            });
            revalidateResourceAndAncestors(result.rid || rid);
          }

          toast({ title: "Success", description: "Element updated successfully" });
          return result;
        } else {
          const { cfg_dict, ...firstLevelFields } = elementData;
          const result = await resourcesApi.createResource({
            teamId,
            category,
            type,
            config: cfg_dict,
            ...firstLevelFields,
          });

          if (result) {
            addOrUpdateResource({
              rid: result.rid,
              name: result.name || elementData.name,
              category: result.category || category,
              type: result.type || type,
            });
            revalidateResourceAndAncestors(result.rid);
          }

          toast({ title: "Success", description: "Element created successfully" });
          return result;
        }
      } catch (err: any) {
        const errorMessage =
          err.response?.data?.error || "Failed to save element";
        setError(errorMessage);
        toast({
          title: "Error",
          description: errorMessage,
          variant: "destructive",
        });
        console.error("Error saving element:", err);
        return null;
      } finally {
        setIsLoading(false);
      }
    },
    [toast, teamId],
  );

  // Delete element using Resources API
  const deleteElement = useCallback(
    async (rid: string) => {
      try {
        setIsLoading(true);
        setError(null);

        await resourcesApi.deleteResource(rid);

        removeResource(rid);

        toast({ title: "Success", description: "Element deleted successfully" });
        return true;
      } catch (err: any) {
        const errorMessage =
          err.response?.data?.error || "Failed to delete element";
        setError(errorMessage);
        toast({
          title: "Error",
          description: errorMessage,
          variant: "destructive",
        });
        console.error("Error deleting element:", err);
        return false;
      } finally {
        setIsLoading(false);
      }
    },
    [toast],
  );

  // Fetch the annotated schema for a built-in resource (same schema as inventory,
  // but each field has a readOnly hint based on the resource's BuiltinSchema)
  const fetchBuiltinSchema = useCallback(
    async (resourceId: string) => {
      try {
        setIsLoading(true);
        setError(null);

        const builtinSchema = await resourcesApi.getBuiltinSchema(resourceId);
        setElementSchema({
          category: "",
          name: "",
          type: "",
          description: "",
          tags: [],
          config_schema: builtinSchema,
        });
        return builtinSchema;
      } catch (err: any) {
        const errorMessage =
          err.response?.data?.error || "Failed to fetch built-in schema";
        setError(errorMessage);
        toast({
          title: "Error",
          description: errorMessage,
          variant: "destructive",
        });
        console.error("Error fetching built-in schema:", err);
        return null;
      } finally {
        setIsLoading(false);
      }
    },
    [toast],
  );

  const fetchBuiltinUserConfig = useCallback(
    async (resourceId: string): Promise<Record<string, any> | null> => {
      try {
        return await resourcesApi.getBuiltinUserConfig({
          resourceId,
          teamId,
        });
      } catch (err: any) {
        console.error("Error fetching built-in user config:", err);
        return null;
      }
    },
    [teamId],
  );

  // Save per-user configuration for a built-in resource (only non-readOnly fields)
  const configureBuiltin = useCallback(
    async (
      resourceId: string,
      config: Record<string, any>,
      options?: { silent?: boolean },
    ) => {
      const silent = options?.silent ?? false;
      try {
        // Silent background writes (e.g. persisting a discovered auth
        // identifier) must not toggle the shared loading state — that would
        // spuriously show a loading spinner elsewhere in the workspace for
        // a save the user didn't initiate.
        if (!silent) setIsLoading(true);
        setError(null);

        const result = await resourcesApi.configureBuiltin({
          resourceId,
          teamId,
          config,
        });

        // Response cfg_dict is overlay-merged for this caller — refresh the
        // local inventory instance so cards (e.g. MCP tool_names) update
        // immediately instead of keeping the shared base config's empty
        // "All tools" fallback until the next full refetch.
        if (result?.cfg_dict) {
          setElementInstances((prev) =>
            prev.map((el) =>
              el.rid === resourceId
                ? {
                    ...el,
                    config: result.cfg_dict,
                    userConfigured: result.user_configured ?? true,
                    updated: result.updated ?? el.updated,
                  }
                : el,
            ),
          );
        }

        // The resource's validation status may have flipped (e.g. a
        // previously-missing token is now set) — the cached badge on the
        // card would otherwise keep showing the pre-save status forever.
        revalidateResourceAndAncestors(resourceId);

        // `silent` is used for background writes (e.g. persisting the
        // discovered auth identifier right after a sign-in flow completes)
        // that aren't a user-initiated "Configure" save and shouldn't pop a
        // toast every time.
        if (!silent) {
          toast({
            title: "Success",
            description: "Built-in resource configured successfully",
          });
        }
        return result;
      } catch (err: any) {
        const errorMessage =
          err.response?.data?.error || "Failed to configure built-in resource";
        setError(errorMessage);
        if (!silent) {
          toast({
            title: "Error",
            description: errorMessage,
            variant: "destructive",
          });
        }
        console.error("Error configuring built-in:", err);
        // Rethrow (rather than returning null) so callers - notably
        // BuiltinConfigureModal's handleSave - know the save failed and
        // don't dismiss the modal as if it had succeeded.
        throw err;
      } finally {
        if (!silent) setIsLoading(false);
      }
    },
    [toast, teamId, revalidateResourceAndAncestors],
  );

  // Create a built-in resource directly (admin only).
  // Configurable keys are derived from the schema's ReadOnlyHint annotations
  // on the backend — no need to pass them from the frontend.
  const saveBuiltinElement = useCallback(
    async (
      category: string,
      type: string,
      elementData: any,
      availableToAll: boolean = false,
      rid?: string,
      expectedVersion?: number,
    ) => {
      try {
        setIsLoading(true);
        setError(null);

        if (rid) {
          if (expectedVersion === undefined) throw new Error('Reload the resource before editing');
          const result = await resourcesApi.updateBuiltin({
            resourceId: rid,
            expectedVersion,
            config: elementData.cfg_dict,
            name: elementData.name,
            execution: elementData.execution,
            availableToAll,
          });
          if (result) {
            addOrUpdateResource({
              rid: result.rid || rid,
              name: result.name || elementData.name,
              category: result.category || category,
              type: result.type || type,
            });
            revalidateResourceAndAncestors(result.rid || rid);
          }
          const cascadeNote = describeCascadedResources(result);
          toast({
            title: "Success",
            description: cascadeNote
              ? `Built-in resource updated successfully. ${cascadeNote}`
              : "Built-in resource updated successfully",
          });
          return result;
        } else {
          const { cfg_dict, name } = elementData;
          const result = await resourcesApi.createBuiltin({
            teamId,
            category,
            type,
            name,
            config: cfg_dict,
            execution: elementData.execution,
            availableToAll,
          });
          if (result) {
            addOrUpdateResource({
              rid: result.rid,
              name: result.name || elementData.name,
              category: result.category || category,
              type: result.type || type,
            });
            revalidateResourceAndAncestors(result.rid);
          }
          const cascadeNote = describeCascadedResources(result);
          toast({
            title: "Success",
            description: cascadeNote
              ? `Built-in resource created successfully. ${cascadeNote}`
              : "Built-in resource created successfully",
          });
          return result;
        }
      } catch (err: any) {
        const errorMessage =
          err.response?.data?.error || "Failed to save built-in resource";
        setError(errorMessage);
        toast({
          title: "Error",
          description: errorMessage,
          variant: "destructive",
        });
        console.error("Error saving built-in element:", err);
        return null;
      } finally {
        setIsLoading(false);
      }
    },
    [toast, teamId, addOrUpdateResource, revalidateResourceAndAncestors],
  );

  // Toggle available_to_all status for a resource (admin only)
  const toggleBuiltinStatus = useCallback(
    async (resourceId: string, availableToAll: boolean, expectedVersion: number) => {
      try {
        setIsLoading(true);
        setError(null);

        const result = await resourcesApi.toggleBuiltinVisibility({
          resourceId,
          expectedVersion,
          availableToAll,
        });

        const cascadeNote = describeCascadedResources(result);
        toast({
          title: "Success",
          description: availableToAll
            ? cascadeNote
              ? `Resource is now available to all users. ${cascadeNote}`
              : "Resource is now available to all users"
            : "Resource is no longer available to all users",
        });
        return result;
      } catch (err: any) {
        const errorMessage =
          err.response?.data?.error || "Failed to toggle resource status";
        setError(errorMessage);
        toast({
          title: "Error",
          description: errorMessage,
          variant: "destructive",
        });
        console.error("Error toggling built-in status:", err);
        return null;
      } finally {
        setIsLoading(false);
      }
    },
    [toast],
  );

  // Delete a built-in/admin resource (admin only)
  const deleteBuiltinElement = useCallback(
    async (rid: string, expectedVersion: number) => {
      try {
        setIsLoading(true);
        setError(null);

        await resourcesApi.deleteBuiltin(rid, expectedVersion);
        removeResource(rid);

        toast({ title: "Success", description: "Built-in resource deleted successfully" });
        return true;
      } catch (err: any) {
        const errorMessage =
          err.response?.data?.error || "Failed to delete built-in resource";
        setError(errorMessage);
        toast({
          title: "Error",
          description: errorMessage,
          variant: "destructive",
        });
        console.error("Error deleting built-in element:", err);
        return false;
      } finally {
        setIsLoading(false);
      }
    },
    [toast, removeResource],
  );

  // Initialize categories on mount
  useEffect(() => {
    fetchCategories();
  }, [fetchCategories]);

  return {
    categories,
    elementInstances,
    elementSchema,
    elementActions,
    isLoading: isLoading || isLoadingSchema || isLoadingActions,
    isLoadingInstances,
    error,
    fetchCategories,
    fetchElementInstances,
    fetchElementSchema,
    fetchElementActions,
    fetchResourcesForCategory,
    fetchResourceById,
    fetchBuiltinSchema,
    fetchBuiltinUserConfig,
    configureBuiltin,
    saveElement,
    deleteElement,
    saveBuiltinElement,
    toggleBuiltinStatus,
    deleteBuiltinElement,
    refetchCategories: fetchCategories,
  };
};
