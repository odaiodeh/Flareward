import { useEffect, useState } from 'react';
import { previewProgramInterface, type ProgramBody, type ProgramInterfacePreview } from '@/api/programs';
import { programError } from './authoring';

/** Draft configuration stays out of shared query caches; superseded responses never drive authoring. */
export function useProgramInterface(body: ProgramBody, enabled: boolean, teamId?: string) {
  const request = JSON.stringify({ implementation: body.implementation, input_schema: body.input_schema, output_schema: body.output_schema, execution_profile: body.execution_profile });
  const [result, setResult] = useState<{ request: string; teamId?: string; preview?: ProgramInterfacePreview; error?: string }>();
  useEffect(() => {
    if (!enabled) return;
    const controller = new AbortController();
    const timer = setTimeout(() => {
      void previewProgramInterface(JSON.parse(request) as ProgramBody, teamId, controller.signal)
        .then(preview => { if (!controller.signal.aborted) setResult({ request, teamId, preview }); })
        .catch(error => { if (!controller.signal.aborted) setResult({ request, teamId, error: programError(error) }); });
    }, 250);
    return () => { clearTimeout(timer); controller.abort(); };
  }, [request, teamId, enabled]);
  const current = enabled && result?.request === request && result.teamId === teamId ? result : undefined;
  return { preview: current?.preview, error: current?.error, pending: enabled && !current };
}
