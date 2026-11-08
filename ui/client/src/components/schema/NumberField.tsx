import React, { useEffect, useRef, useState } from 'react';
import type { JsonObject, JsonValue } from '@shared/json';
import { Input } from '@/components/ui/input';
import { parseSchemaNumber } from './schema';

/** Keep raw numeric edits visible until they can safely update the portable value. */
export default function NumberField({ label, schema, value, onChange, disabled, required }: {
  label: string; schema: JsonObject; value: JsonValue | undefined;
  onChange: (value: number | undefined) => void; disabled: boolean; required: boolean;
}) {
  const serialized = typeof value === 'number' ? String(value) : '';
  const [text, setText] = useState(serialized);
  const [error, setError] = useState('');
  const lastValue = useRef(serialized);
  const input = useRef<HTMLInputElement>(null);
  useEffect(() => {
    if (lastValue.current !== serialized) {
      setText(serialized); setError(''); input.current?.setCustomValidity(''); lastValue.current = serialized;
    }
  }, [serialized]);
  return <label className="block space-y-1 text-sm"><span>{label}</span>
    <Input ref={input} aria-label={label} inputMode={schema.type === 'integer' ? 'numeric' : 'decimal'} required={required} disabled={disabled} value={text} onChange={event => {
      setText(event.target.value);
      try {
        const parsed = parseSchemaNumber(event.target.value, schema);
        event.target.setCustomValidity(''); setError(''); lastValue.current = parsed === undefined ? '' : String(parsed); onChange(parsed);
      } catch (failure) {
        const message = failure instanceof Error ? failure.message : 'Enter a valid number.';
        event.target.setCustomValidity(message); setError(message);
      }
    }} />{error && <span role="alert" className="text-destructive">{error}</span>}
  </label>;
}
