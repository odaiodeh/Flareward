import React, { useEffect, useRef, useState } from 'react';
import type { JsonValue } from '@shared/json';
import { Textarea } from '@/components/ui/textarea';

/** Invalid edits stay visible and block form submission instead of saving an old value. */
export default function JsonField({ label, value, onChange, disabled, objectOnly = false }: {
  label: string; value: JsonValue; onChange: (value: JsonValue) => void; disabled?: boolean; objectOnly?: boolean;
}) {
  const serialized = JSON.stringify(value, null, 2);
  const [text, setText] = useState(serialized);
  const [error, setError] = useState('');
  const lastValue = useRef(serialized);
  const input = useRef<HTMLTextAreaElement>(null);
  useEffect(() => {
    if (lastValue.current !== serialized) {
      setText(serialized); setError(''); input.current?.setCustomValidity(''); lastValue.current = serialized;
    }
  }, [serialized]);
  return <label className="block space-y-1 text-sm"><span>{label}</span>
    <Textarea ref={input} aria-label={label} className="font-mono" rows={4} value={text} disabled={disabled} onChange={event => {
      setText(event.target.value);
      try {
        const parsed = JSON.parse(event.target.value) as JsonValue;
        if (objectOnly && (parsed === null || Array.isArray(parsed) || typeof parsed !== 'object')) throw new Error('Enter a JSON object.');
        event.target.setCustomValidity(''); setError(''); lastValue.current = JSON.stringify(parsed, null, 2); onChange(parsed);
      } catch {
        const message = objectOnly ? 'Enter a valid JSON object.' : 'Enter valid JSON.';
        event.target.setCustomValidity(message); setError(message);
      }
    }} />{error && <span role="alert" className="text-destructive">{error}</span>}
  </label>;
}
