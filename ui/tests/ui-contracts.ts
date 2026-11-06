/** UI-owned contracts use plain data and transport doubles, without a browser or LLM. */
import assert from 'node:assert/strict';
import React from 'react';
import { renderToStaticMarkup } from 'react-dom/server';
import SchemaValue from '../client/src/components/schema/SchemaValue';
import axios from '../client/src/http/axiosAgentConfig';
import { acquireTeamEditLock, heartbeatTeamEditLock, releaseTeamEditLock } from '../client/src/api/collaborationEditLock';
import { getSessionState } from '../client/src/api/sessions';
import { readSessionEvents } from '../client/src/api/session-stream';
import { isRecord } from '../client/src/lib/json';
import { graphFlowToLayoutData } from '../client/src/utils/graphFlowLayout';
import { buildElementBlockMap } from '../client/src/components/agentic-ai/graphs/GraphDisplayHelpers';
import type { GraphFlow } from '../client/src/components/agentic-ai/graphs/interfaces';
import { sameApproval, updateApproval } from '../client/src/components/agentic-ai/chat/types';
import type { ApprovalEntry, NodeEntry } from '../client/src/components/agentic-ai/chat/types';
import { elementFormSchema, toElementInstance } from '../client/src/lib/resource-editor';
import type { ElementSchema } from '../client/src/types/workspace';
import { applyWorkflowPlacement, workflowPlacement } from '../client/src/lib/workflow-placement';
import { reconstructBlueprintGraph } from '../client/src/hooks/use-load-blueprint';
import type { YamlFlowState } from '../client/src/types/graph';
import type { JsonObject } from '../shared/json';
import { configurationDefaults } from '../client/src/features/programs/authoring';
import { initialSchemaInput, resolveSchema } from '../client/src/components/schema/schema';
import { verifyProgramGraphEditing } from './program-graph-contracts';
import { verifyArtifactContracts } from './artifact-contracts';

function verifyProgramConfigurationSchemas() {
  assert.deepEqual(initialSchemaInput({ type: 'array' }), []);
  assert.equal(initialSchemaInput({ type: 'boolean' }), null);
  const defaultInput: JsonObject = { $defs: { Input: { type: 'object', default: { criteria: ['test'] } } }, $ref: '#/$defs/Input' };
  const copied = initialSchemaInput(defaultInput) as JsonObject;
  (copied.criteria as string[]).push('review');
  assert.deepEqual(initialSchemaInput(defaultInput), { criteria: ['test'] });
  const schema: JsonObject = {
    $defs: { Policy: { type: 'string', enum: ['required', 'optional'] }, Recursive: { anyOf: [{ $ref: '#/$defs/Recursive' }, { type: 'null' }] } },
    properties: { policy: { $ref: '#/$defs/Policy', default: 'required' }, options: { type: 'object', default: { checks: ['test'] } } },
  };
  assert.deepEqual(resolveSchema(schema, { $ref: '#/$defs/Policy', default: 'required' })?.enum, ['required', 'optional']);
  assert.equal(resolveSchema(schema, { $ref: 'https://example.invalid/schema' }), null);
  assert.equal(resolveSchema(schema, { $ref: '#/$defs/Recursive' }), null);
  const descriptor = { key: 'engineering', version: '1', name: 'Engineering', description: '', configuration_schema: schema, input_schema: null, output_schema: null };
  const first = configurationDefaults(descriptor);
  assert.deepEqual(first, { policy: 'required', options: { checks: ['test'] } });
  (first.options as { checks: string[] }).checks.push('review');
  assert.deepEqual(configurationDefaults(descriptor).options, { checks: ['test'] });

  const nested: JsonObject = {
    type: 'object', additionalProperties: false,
    $defs: { Rule: { type: 'object', title: 'InternalRuleModel', properties: { text: { type: 'string', title: 'Acceptance criterion' } }, required: ['text'] } },
    properties: {
      criteria: { type: 'array', title: 'Criteria', items: { $ref: '#/$defs/Rule' }, maxItems: 2 },
      optional: { type: 'string', title: 'Optional note' },
      dynamic: { anyOf: [{ type: 'string' }, { type: 'object' }] },
    }, required: ['criteria', 'dynamic'],
  };
  const values = { criteria: [{ text: '<script>unsafe()</script>' }], dynamic: { variant: 'custom' } };
  const before = JSON.stringify(values);
  const rendered = renderToStaticMarkup(React.createElement(SchemaValue, {
    schema: nested, label: 'Feature input', value: values, onChange: () => assert.fail('Rendering changed input'),
  }));
  assert.ok(rendered.includes('Acceptance criterion'));
  assert.ok(rendered.includes('Configure Optional note'));
  assert.ok(rendered.includes('Add Criteria'));
  assert.ok(rendered.includes('variant'));
  assert.ok(!rendered.includes('InternalRuleModel'));
  assert.ok(!rendered.includes('<script>unsafe'));
  assert.equal(JSON.stringify(values), before);

  const recursive: JsonObject = { type: 'object', properties: { child: { $ref: '#' } }, required: ['child'] };
  const fallback = renderToStaticMarkup(React.createElement(SchemaValue, {
    schema: recursive, label: 'Recursive input', value: {}, onChange: () => assert.fail('Rendering changed input'),
  }));
  assert.ok(fallback.includes('textarea'));
}

function verifyWorkflowPlacement() {
  const flow: YamlFlowState = {
    name: 'Placed workflow', execution_profile: 'isolated', environments: { coding: 'isolated' },
    nodes: [{ rid: 'agent', name: 'Agent' }],
    plan: [{ uid: 'work', node: 'agent', execution: { environment: 'coding' } }],
  };
  const saved = JSON.stringify(flow);
  const choices = workflowPlacement(flow);
  choices.steps.work.execution = {};
  const updated = applyWorkflowPlacement(flow, choices);
  assert.deepEqual(updated.plan[0].execution, {});
  assert.equal(updated.execution_profile, 'isolated');
  assert.deepEqual(updated.environments, { coding: 'isolated' });
  assert.equal(JSON.stringify(flow), saved);
  assert.deepEqual(reconstructBlueprintGraph(flow, [], []).yamlFlow, { ...flow, description: '', conditions: [] });
}

function verifyResourceEditorBoundaries() {
  const element: ElementSchema = {
    category: 'nodes', type: 'fixture', name: 'Fixture', description: '', tags: [],
    config_schema: {
      type: 'object', properties: { prompt: { type: 'string' } }, required: ['prompt'],
      additionalProperties: false, $defs: { Dependency: { type: 'object' } },
    },
  };
  const combined = elementFormSchema(element, {
    properties: { name: { type: 'string' }, execution: { $ref: '#/$defs/Execution' }, identity: {} },
    required: ['name', 'identity', 'execution'],
  });
  assert.deepEqual(Object.keys(combined.config_schema.properties), ['name', 'prompt']);
  assert.deepEqual(combined.config_schema.required, ['name', 'prompt']);
  assert.equal(combined.config_schema.$defs, element.config_schema.$defs);
  const optionalConfig = { ...element, config_schema: { ...element.config_schema, required: undefined } };
  assert.deepEqual(elementFormSchema(optionalConfig, { required: ['name'] }).config_schema.required, ['name']);
  const instance = toElementInstance({
    rid: 'agent', identity: { type: 'user', id: 'owner', display_name: 'Owner' },
    category: 'nodes', type: 'fixture', name: 'Agent', cfg_dict: { prompt: 'Work' },
    execution: { profile: 'isolated' }, version: 7, nested_refs: [], created: '', updated: '',
  });
  assert.deepEqual(instance.execution, { profile: 'isolated' });
  assert.deepEqual(instance.config, { prompt: 'Work' });
  assert.equal(instance.version, 7);
}

function verifyApprovalIdentity() {
  const approval = (executionId: string): ApprovalEntry => ({
    executionId, requestId: 'same-request', toolName: 'write', toolArgs: {},
    toolDescription: 'Write', accessMode: 'write', originNodeUid: 'agent',
    originNodeName: 'Agent', status: 'pending',
  });
  const old = approval('old-root'), current = approval('new-root');
  const entries: NodeEntry[] = [{
    node_name: 'Agent', node_uid: 'agent', stream: 'PROGRESS', text: '',
    tools: [], workplans: [], approvals: [old, current],
  }];
  assert.equal(sameApproval(old, current), false);
  assert.equal(updateApproval(entries, current, 'approved', 'Reviewed'), true);
  assert.equal(old.status, 'pending');
  assert.equal(current.status, 'approved');
  assert.equal(current.feedback, 'Reviewed');
  assert.equal(updateApproval(entries, { requestId: 'same-request' }, 'rejected'), false);
  assert.equal(updateApproval(entries, { requestId: 'same-request', executionId: 'missing' }, 'rejected'), false);
  assert.equal(updateApproval(entries, old, 'rejected'), true);
  assert.equal(current.status, 'approved');
  assert.equal(old.status, 'rejected');
}

function verifyGraphReferences() {
  const config = { type: 'openai', model_name: 'fixture-model' };
  const graph: GraphFlow = {
    name: 'Saved references', description: 'Display saved node/model references',
    llms: [{ rid: '$ref:model', name: 'Saved model', type: 'openai', config }],
    nodes: [{
      rid: '$ref:agent', name: 'Saved agent', type: 'custom_agent_node',
      config: { type: 'custom_agent_node', llm: '$ref:model' },
    }],
    plan: [{ uid: 'run-agent', node: '$ref:agent', exit_condition: null,
      meta: { display_name: 'Agent step', description: 'Work', tags: [] } }],
  };
  const layout = graphFlowToLayoutData(graph);
  assert.equal(layout.nodes[0].id, 'run-agent');
  assert.equal(layout.nodes[0].label, 'Agent step');
  assert.deepEqual(layout.nodes[0].resolvedElements, [{ type: 'llm', name: 'Saved model', id: 'model', config }]);
  assert.deepEqual(buildElementBlockMap(layout.nodes, graph).get('model')?.workspaceData?.config, config);

  // Malformed remote metadata cannot be presented as an element configuration object.
  const malformed = JSON.parse(JSON.stringify(graph));
  malformed.llms[0].config = [];
  const invalidLayout = graphFlowToLayoutData(malformed);
  assert.equal(invalidLayout.nodes[0].resolvedElements[0].config, undefined);
  assert.deepEqual(buildElementBlockMap(invalidLayout.nodes, malformed).get('model')?.workspaceData?.config, {});
  assert.equal(isRecord(null), false);
  assert.equal(isRecord([]), false);
}

async function verifySessionOutputContract() {
  const previous = axios.defaults.adapter;
  try {
    axios.defaults.adapter = async config => {
      assert.equal(config.url, '/sessions/session.state.get?sessionId=run%2Fwith+space');
      return { data: { output: 'Agent answer' }, status: 200, statusText: 'OK', headers: {}, config };
    };
    assert.deepEqual(await getSessionState('run/with space'), { output: 'Agent answer' });
    for (const output of [undefined, null, 42, { private: 'private-output-value' }]) {
      axios.defaults.adapter = async config => ({
        data: { output }, status: 200, statusText: 'OK', headers: {}, config,
      });
      await assert.rejects(getSessionState('run'), error => {
        assert.ok(error instanceof Error);
        assert.equal(error.message, 'Session state contains an invalid output');
        assert.ok(!error.message.includes('private-output-value'));
        return true;
      });
    }
  } finally {
    axios.defaults.adapter = previous;
  }
}

export default async function verifyUiContracts() {
  await verifyArtifactContracts();
  verifyProgramConfigurationSchemas();
  verifyProgramGraphEditing();
  verifyWorkflowPlacement();
  verifyResourceEditorBoundaries();
  verifyGraphReferences();
  verifyApprovalIdentity();
  await verifySessionOutputContract();
  await verifyEditingLeaseOwnership();
  await verifyStreamFramingAndOwnership();
  console.log('UI graph and session output contracts passed');
}

async function verifyEditingLeaseOwnership() {
  const previous = axios.defaults.adapter;
  const editor = {
    teamId: 'team', entityKind: 'resource' as const, entityId: 'resource',
    userId: 'actor', displayName: 'Actor', leaseId: 'editor-occurrence',
  };
  const calls: string[] = [];
  let renewed = true;
  try {
    axios.defaults.adapter = async config => {
      assert.equal(JSON.parse(config.data).leaseId, editor.leaseId);
      calls.push(config.url!);
      return { config, data: { acquired: true, renewed }, status: 200, statusText: 'OK', headers: {} };
    };
    assert.deepEqual(await acquireTeamEditLock(editor), { acquired: true });
    await heartbeatTeamEditLock(editor);
    renewed = false;
    await assert.rejects(heartbeatTeamEditLock(editor), /Editing lease expired/);
    await releaseTeamEditLock(editor);
    assert.deepEqual(calls, [
      '/collaboration/edit_lock.acquire', '/collaboration/edit_lock.heartbeat',
      '/collaboration/edit_lock.heartbeat', '/collaboration/edit_lock.release',
    ]);
  } finally {
    axios.defaults.adapter = previous;
  }
}

async function verifyStreamFramingAndOwnership() {
  const bytes = new TextEncoder().encode(
    '{"type":"llm_token","chunk":"שלום"}\n["custom",{"type":"complete"}]\n{"type":"stream_end"}',
  );
  const response = new Response(new ReadableStream({
    start(controller) {
      for (const byte of bytes) controller.enqueue(new Uint8Array([byte]));
      controller.close();
    },
  }));
  const events = [];
  for await (const event of readSessionEvents(response)) events.push(event);
  assert.deepEqual(events, [
    { type: 'llm_token', chunk: 'שלום' }, { type: 'complete' }, { type: 'stream_end' },
  ]);
  assert.equal(response.body?.locked, false);
  let cancelled = false;
  const open = new Response(new ReadableStream({
    pull(controller) { controller.enqueue(new TextEncoder().encode('{"type":"heartbeat"}\n')); },
    cancel() { cancelled = true; },
  }));
  for await (const _event of readSessionEvents(open)) break;
  assert.equal(cancelled, true);
  assert.equal(open.body?.locked, false);
  const malformed = new Response('{"private-token":"do-not-echo"');
  await assert.rejects(async () => {
    for await (const _event of readSessionEvents(malformed)) assert.fail('Invalid input was accepted');
  }, { message: 'Session stream contains an invalid event' });
}
