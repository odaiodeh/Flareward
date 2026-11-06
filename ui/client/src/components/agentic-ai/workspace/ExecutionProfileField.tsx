import { useId } from 'react';
import { useExecutionProfiles } from '@/hooks/use-execution-profiles';

interface Props {
  teamId?: string;
  value: string;
  onChange: (profile: string) => void;
}

export function ExecutionProfileField({ value, onChange, teamId }: Props) {
  const id = useId();
  const { data, isPending, isError } = useExecutionProfiles(teamId);
  const unavailable = !!value && !!data && !data.profiles.includes(value);
  return (
    <div className="space-y-2 border-t border-gray-800 pt-4">
      <label htmlFor={id} className="text-sm font-medium">Run environment</label>
      <select
        id={id}
        value={value}
        onChange={event => onChange(event.target.value)}
        disabled={isPending || isError}
        className="w-full rounded-md border border-input bg-background px-3 py-2 text-sm"
        aria-describedby={`${id}-help`}
      >
        <option value="">Use workflow default{data ? ` (platform: ${data.default_profile})` : ''}</option>
        {value && !data?.profiles.includes(value) && (
          <option value={value} disabled>{value} ({data ? 'unavailable' : 'saved'})</option>
        )}
        {data?.profiles.map(profile => <option key={profile} value={profile}>{profile}</option>)}
      </select>
      <p id={`${id}-help`} className="text-xs text-muted-foreground">
        {isError ? 'Could not load approved environments. The saved choice is preserved.'
          : unavailable ? 'This saved environment is no longer approved. Select an available environment before running.'
          : 'Saved with this element. A workflow step can override this preference.'}
      </p>
    </div>
  );
}
