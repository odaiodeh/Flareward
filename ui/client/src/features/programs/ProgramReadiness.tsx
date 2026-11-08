import React from 'react';
import { CircleCheck, CircleAlert, RefreshCw } from 'lucide-react';
import type { ProgramValidation } from '@/api/programs';

/** Presents the application's saved-definition assessment without inventing runtime admission. */
export default function ProgramReadiness({ report, current }: { report: ProgramValidation; current: boolean }) {
  const Icon = !current ? RefreshCw : report.valid ? CircleCheck : CircleAlert;
  const title = !current ? 'Definition changed since this check' : report.valid ? 'Definition ready to publish' : 'Complete the definition before publishing';
  return <section aria-label="Program readiness" className="rounded-lg border bg-muted/20 p-4 space-y-3">
    <div role="status" className="flex items-start gap-3">
      <Icon aria-hidden="true" className={`mt-0.5 h-5 w-5 shrink-0 ${!current ? 'text-muted-foreground' : report.valid ? 'text-emerald-500' : 'text-amber-500'}`} />
      <div><h3 className="text-sm font-medium">{title}</h3><p className="mt-1 text-xs text-muted-foreground">
        {!current ? 'Check readiness again to assess your latest changes.' : `Checked saved draft version ${report.version}. Execution permissions, placement and inputs are checked when you run.`}
      </p></div>
    </div>
    {current && report.issues.length > 0 && <ul className="space-y-3 pl-8 text-sm">{report.issues.map((issue, index) => <li key={index}>
      <p>{issue.message}</p>
      {issue.path.length > 0 && <p className="mt-1 break-words text-xs text-muted-foreground">{issue.path.map(part => typeof part === 'number' ? `Item ${part + 1}` : part).join(' / ')}</p>}
    </li>)}</ul>}
  </section>;
}
