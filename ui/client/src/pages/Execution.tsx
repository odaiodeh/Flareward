import React from 'react';
import { useRoute } from 'wouter';
import ExecutionWorkbench from '@/components/executions/ExecutionWorkbench';
import { useWorkspaceIdentity } from '@/hooks/use-workspace-identity';

export default function Execution() {
  const [, params] = useRoute('/executions/:executionId');
  const owner = useWorkspaceIdentity();
  const scope = JSON.stringify([owner.isTeam, owner.userId, owner.credentialUserId]);
  if (!params?.executionId) return null;
  return <main className="dark-inputs h-full overflow-auto p-6"><ExecutionWorkbench key={JSON.stringify([scope, params.executionId])} id={params.executionId} scope={scope} teamId={owner.teamId} human={owner.credentialUserId} /></main>;
}
