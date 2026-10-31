import axios from '@/http/axiosAgentConfig';

export interface CatalogResponse {
  elements: { [category: string]: any[] };
}

export interface ExecutionProfileCatalog {
  profiles: string[];
  default_profile: string;
  environment_profiles: string[];
}

export const catalogService = {
  async fetchExecutionProfiles(signal?: AbortSignal): Promise<ExecutionProfileCatalog> {
    const response = await axios.get<ExecutionProfileCatalog>("/catalog/execution-profiles", { signal });
    return response.data;
  },
  /**
   * Fetch all available element categories and types from the catalog.
   * Returns a map of category names to arrays of element types.
   */
  async fetchAllElements(): Promise<CatalogResponse> {
    const response = await axios.get<CatalogResponse>("/catalog/elements.list.get");
    return response.data;
  },

  /**
   * Get all category names from the catalog.
   * Returns an array of lowercase category names.
   */
  async fetchCategories(): Promise<string[]> {
    try {
      const catalogResponse = await this.fetchAllElements();
      return Object.keys(catalogResponse.elements).map(cat => cat.toLowerCase());
    } catch (err: any) {
      console.warn("Failed to fetch categories from catalog, using fallback:", err);
      // Fallback categories if API call fails
      return ['nodes', 'llms', 'tools', 'providers', 'retrievers', 'conditions'];
    }
  },
};

