import React, { useState } from 'react';
import type { JsonObject, JsonValue } from '@shared/json';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { isRecord } from '@/lib/json';
import JsonField from './JsonField';
import NumberField from './NumberField';
import { resolveSchema } from './schema';

export interface SchemaField {
  schema: JsonObject; value: JsonValue | undefined; label: string; path: string;
  disabled: boolean; onChange: (value: JsonValue | undefined) => void;
}

export type FieldRenderer = (field: SchemaField) => React.ReactNode;

/** Presentation only. Unsupported schemas keep an explicit JSON editor. */
export default function SchemaValue({ schema: raw, root = raw, value, onChange, label, path = '', disabled = false, required = true, depth = 0, renderField }: {
  schema: JsonObject; root?: JsonObject; value: JsonValue | undefined;
  onChange: (value: JsonValue | undefined) => void; label: string; path?: string;
  disabled?: boolean; required?: boolean; depth?: number; renderField?: FieldRenderer;
}) {
  const schema = resolveSchema(root, raw);
  const fieldLabel = typeof raw.title === 'string' && depth > 0 ? raw.title : label;
  const description = typeof schema?.description === 'string' ? schema.description : '';
  const custom = schema && renderField?.({ schema, value, onChange, label: fieldLabel, path, disabled });
  let editor: React.ReactNode;
  if (custom) editor = custom;
  else if (!required && value === undefined) editor = <Button type="button" variant="outline" disabled={disabled} onClick={() => onChange(initialValue(schema))}>Configure {fieldLabel}</Button>;
  else if (!schema || depth >= 12 || schema.anyOf || schema.oneOf || schema.allOf) editor = <JsonField label={fieldLabel} value={value ?? null} objectOnly={depth === 0 && schema?.type === 'object' && !raw.anyOf && !raw.oneOf} disabled={disabled} onChange={onChange} />;
  else if (Array.isArray(schema.enum)) editor = <label className="block text-sm">{fieldLabel}<select aria-label={fieldLabel} className="block w-full rounded border bg-background p-2" disabled={disabled} required={required} value={JSON.stringify(value) ?? ''} onChange={event => onChange(event.target.value ? JSON.parse(event.target.value) as JsonValue : undefined)}>
    <option value="">Select a value</option>{schema.enum.map(choice => <option key={JSON.stringify(choice)} value={JSON.stringify(choice)}>{typeof choice === 'object' ? JSON.stringify(choice) : String(choice)}</option>)}
  </select></label>;
  else if (schema.type === 'object' && isRecord(schema.properties) && Object.keys(schema.properties).length && schema.additionalProperties !== true && !isRecord(schema.additionalProperties)) {
    const object = isRecord(value) ? value as JsonObject : {};
    const requiredFields = Array.isArray(schema.required) ? schema.required : [];
    editor = <fieldset className="space-y-3 rounded border p-3" disabled={disabled}><legend className="px-1 text-sm font-medium">{fieldLabel}</legend>
      {Object.entries(schema.properties).map(([name, child]) => <SchemaValue key={name} schema={isRecord(child) ? child as JsonObject : {}} root={root} value={object[name]} label={name} path={`${path}/${name.replace(/~/g, '~0').replace(/\//g, '~1')}`} disabled={disabled} required={requiredFields.includes(name)} depth={depth + 1} renderField={renderField} onChange={next => {
        const updated = { ...object }; if (next === undefined) delete updated[name]; else updated[name] = next; onChange(updated);
      }} />)}
    </fieldset>;
  } else if (schema.type === 'array' && isRecord(schema.items)) {
    editor = <SchemaArray schema={schema} root={root} items={Array.isArray(value) ? value : []} label={fieldLabel} path={path} disabled={disabled} depth={depth} renderField={renderField} onChange={onChange} />;
  } else if (schema.type === 'boolean') editor = <label className="block text-sm">{fieldLabel}<select aria-label={fieldLabel} className="block w-full rounded border bg-background p-2" disabled={disabled} required={required} value={typeof value === 'boolean' ? String(value) : ''} onChange={event => onChange(event.target.value === '' ? undefined : event.target.value === 'true')}>
    <option value="">Select a value</option><option value="true">Yes</option><option value="false">No</option>
  </select></label>;
  else if (schema.type === 'integer' || schema.type === 'number') editor = <NumberField label={fieldLabel} schema={schema} value={value} onChange={onChange} disabled={disabled} required={required} />;
  else if (schema.type === 'string') editor = <label className="block space-y-1 text-sm"><span>{fieldLabel}</span><Input aria-label={fieldLabel} disabled={disabled} required={required}
    type={schema.writeOnly === true || schema.format === 'password' ? 'password' : 'text'}
    autoComplete={schema.writeOnly === true ? 'off' : undefined} value={typeof value === 'string' ? value : ''}
    minLength={typeof schema.minLength === 'number' ? schema.minLength : undefined} maxLength={typeof schema.maxLength === 'number' ? schema.maxLength : undefined}
    onChange={event => onChange(event.target.value)} /></label>;
  else editor = <JsonField label={fieldLabel} value={value ?? null} objectOnly={depth === 0 && schema?.type === 'object' && !raw.anyOf && !raw.oneOf} disabled={disabled} onChange={onChange} />;
  return <div className="space-y-1">{editor}
    {description && !custom && <p className="text-xs text-muted-foreground">{description}</p>}
    {!required && value !== undefined && <Button type="button" variant="ghost" disabled={disabled} onClick={() => onChange(undefined)}>Use default for {fieldLabel}</Button>}
  </div>;
}

function initialValue(schema: JsonObject | null): JsonValue {
  if (schema && Object.hasOwn(schema, 'default')) return structuredClone(schema.default);
  if (schema?.type === 'array') return [];
  if (schema?.type === 'object') return {};
  if (schema?.type === 'boolean') return false;
  return schema?.type === 'number' || schema?.type === 'integer' ? 0 : '';
}

/** Stable row identities preserve unrelated unfinished edits when an item is removed. */
function SchemaArray({ schema, root, items, label, path, disabled, depth, renderField, onChange }: {
  schema: JsonObject; root: JsonObject; items: JsonValue[]; label: string; path: string;
  disabled: boolean; depth: number; renderField?: FieldRenderer; onChange: (value: JsonValue) => void;
}) {
  const [keys, setKeys] = useState(() => items.map(() => crypto.randomUUID()));
  // External replacement may resize the array; local add/remove updates both together.
  if (keys.length !== items.length) setKeys(items.map(() => crypto.randomUUID()));
  const itemSchema = schema.items as JsonObject;
  return <fieldset className="space-y-3 rounded border p-3" disabled={disabled}><legend className="px-1 text-sm font-medium">{label}</legend>
    {items.map((item, index) => <div key={keys[index]} className="space-y-2"><SchemaValue schema={itemSchema} root={root} value={item} label={`${label} ${index + 1}`} path={`${path}/${index}`} disabled={disabled} depth={depth + 1} renderField={renderField} onChange={next => onChange(items.map((old, position) => position === index ? next ?? null : old))} />
      <Button type="button" variant="ghost" disabled={disabled || typeof schema.minItems === 'number' && items.length <= schema.minItems} onClick={() => {
        setKeys(keys.filter((_, position) => position !== index)); onChange(items.filter((_, position) => position !== index));
      }}>Remove {label} {index + 1}</Button>
    </div>)}
    <Button type="button" variant="outline" disabled={disabled || typeof schema.maxItems === 'number' && items.length >= schema.maxItems} onClick={() => {
      setKeys([...keys, crypto.randomUUID()]); onChange([...items, initialValue(resolveSchema(root, itemSchema))]);
    }}>Add {label}</Button>
  </fieldset>;
}
