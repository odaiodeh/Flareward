import type { ReactNode } from "react";
import type { ResourceExecutionDefaults } from './workspace';

export interface ExecutionSelection {
  profile?: string | null;
  environment?: string | null;
}

export interface WorkflowPlacement {
  execution_profile: string | null;
  environments: Record<string, string>;
  steps: Record<string, {
    execution?: ExecutionSelection | null;
    condition_execution?: ExecutionSelection | null;
  }>;
}

export interface BuildingBlock {
  id: string;
  type: string;
  label: string;
  color: string;
  description: string;
  workspaceData?: WorkspaceData;
}

export interface WorkspaceData {
  rid: string;
  name: string;
  category: string;
  type: string;
  config: Record<string, unknown>;
  execution?: ResourceExecutionDefaults;
  version: number;
  created: string;
  updated: string;
  nested_refs: string[];
}

// ---------------------------------------------------------------------------
// Library-agnostic canvas types (no ReactFlow / JointJS dependency)
// ---------------------------------------------------------------------------

export interface CanvasNodeData {
  label: string;
  icon: ReactNode;
  color: string;
  style: string;
  description: string;
  workspaceData?: WorkspaceData;
  onDelete?: (id: string) => void;
  allBlocks?: BuildingBlock[];
  referencedConditions?: BuildingBlock[];
  onAttachCondition?: (nodeId: string, condition: BuildingBlock) => void;
  onRemoveCondition?: (nodeId: string, conditionRid: string) => void;
  isConnectionSource?: boolean;
  isConnectionTarget?: boolean;
}

export interface CanvasNode {
  id: string;
  position: { x: number; y: number };
  data: CanvasNodeData;
  selected?: boolean;
  width?: number;
  height?: number;
}

export interface CanvasEdge {
  id: string;
  source: string;
  target: string;
  data?: {
    label?: string;
    isConditional?: boolean;
  };
}

export interface CurrentGraph {
  id: string;
  name: string;
  nodes: CanvasNode[];
  edges: CanvasEdge[];
  metadata: {
    created: Date;
    lastModified: Date;
    nodeCount: number;
    edgeCount: number;
  };
}

// ---------------------------------------------------------------------------
// YAML flow types (shared by graph-logic, blueprint loading, etc.)
// ---------------------------------------------------------------------------

export interface YamlFlowNode {
  rid: string;
  name: string;
  type?: string;
  config?: Record<string, unknown>;
  execution?: ResourceExecutionDefaults;
}

export interface YamlFlowPlanStep {
  uid: string;
  node: string;
  after?: string | string[] | null;
  branches?: Record<string, string>;
  exit_condition?: string;
  execution?: ExecutionSelection | null;
  condition_execution?: ExecutionSelection | null;
}

export interface YamlFlowCondition {
  rid: string;
  name: string;
  type?: string;
  config?: Record<string, unknown>;
  execution?: ResourceExecutionDefaults;
}

export interface YamlFlowState {
  name?: string;
  description?: string;
  nodes: YamlFlowNode[];
  plan: YamlFlowPlanStep[];
  conditions?: YamlFlowCondition[];
  execution_profile?: string | null;
  environments?: Record<string, string>;
}
