import { useId } from "react";
import type { ChangeEvent } from "react";
import { Input } from "@runsight/ui/input";
import { Label } from "@runsight/ui/label";
import { Switch } from "@runsight/ui/switch";
import { Textarea } from "@runsight/ui/textarea";
import type { WorkflowInputSchemaItem } from "@runsight/shared/zod";

type WorkflowInputSchema = Record<string, WorkflowInputSchemaItem>;
type WorkflowInputValues = Record<string, unknown>;
type WorkflowInputErrors = Partial<Record<string, string>>;

export interface WorkflowInputsFormProps {
  schema: WorkflowInputSchema;
  values: WorkflowInputValues;
  errors?: WorkflowInputErrors;
  disabled?: boolean;
  submitting?: boolean;
  onChange: (name: string, value: unknown) => void;
}

export function WorkflowInputsForm({
  schema,
  values,
  errors = {},
  disabled = false,
  submitting = false,
  onChange,
}: WorkflowInputsFormProps) {
  const formId = useId();
  const controlsDisabled = disabled || submitting;

  return (
    <div className="space-y-4" aria-busy={submitting || undefined}>
      {Object.entries(schema).map(([name, item]) => {
        const label = humanizeInputName(name);
        const value = getInputValue(values, name, item);
        const error = errors[name];
        const isRequired = item.required === true;
        const fieldId = `${formId}-${toDomId(name)}`;
        const descriptionId = item.description ? `${fieldId}-description` : undefined;
        const errorId = error ? `${fieldId}-error` : undefined;
        const describedBy = [descriptionId, errorId].filter(Boolean).join(" ") || undefined;

        return (
          <div key={name} className="space-y-1.5">
            <Label id={`${fieldId}-label`} htmlFor={fieldId} required={isRequired}>
              {label}
            </Label>
            {renderInputControl({
              id: fieldId,
              labelId: `${fieldId}-label`,
              item,
              name,
              value,
              disabled: controlsDisabled,
              required: isRequired,
              invalid: Boolean(error),
              describedBy,
              onChange,
            })}
            {item.description && (
              <p id={descriptionId} className="text-xs text-muted">
                {item.description}
              </p>
            )}
            {error && (
              <p id={errorId} className="text-xs text-danger-11">
                {error}
              </p>
            )}
          </div>
        );
      })}
    </div>
  );
}

function renderInputControl({
  id,
  labelId,
  item,
  name,
  value,
  disabled,
  required,
  invalid,
  describedBy,
  onChange,
}: {
  id: string;
  labelId: string;
  item: WorkflowInputSchemaItem;
  name: string;
  value: unknown;
  disabled: boolean;
  required: boolean;
  invalid: boolean;
  describedBy: string | undefined;
  onChange: (name: string, value: unknown) => void;
}) {
  const sharedProps = {
    id,
    disabled,
    "aria-required": required || undefined,
    "aria-invalid": invalid || undefined,
    "aria-describedby": describedBy,
  };

  switch (item.type) {
    case "number":
      return (
        <Input
          {...sharedProps}
          type="number"
          value={formatNumberValue(value)}
          error={invalid}
          onChange={(event) => onChange(name, parseNumberValue(event.target.value))}
        />
      );
    case "boolean":
      return (
        <Switch
          id={id}
          checked={toBooleanValue(value)}
          disabled={disabled}
          aria-labelledby={labelId}
          aria-required={required || undefined}
          aria-invalid={invalid || undefined}
          aria-describedby={describedBy}
          onCheckedChange={(checked) => onChange(name, checked)}
        />
      );
    case "json":
      return (
        <Textarea
          {...sharedProps}
          code
          value={formatJsonValue(value)}
          onChange={(event) => onChange(name, parseStructuredValue(event))}
        />
      );
    case "array":
      return (
        <Textarea
          {...sharedProps}
          code
          value={formatJsonValue(value)}
          onChange={(event) => onChange(name, parseStructuredValue(event))}
        />
      );
    case "string":
    default:
      return (
        <Input
          {...sharedProps}
          type="text"
          value={toStringValue(value)}
          error={invalid}
          onChange={(event) => onChange(name, event.target.value)}
        />
      );
  }
}

function getInputValue(
  values: WorkflowInputValues,
  name: string,
  item: WorkflowInputSchemaItem,
) {
  return Object.hasOwn(values, name) && values[name] !== undefined
    ? values[name]
    : item.default;
}

function humanizeInputName(name: string) {
  return name
    .replace(/[_-]+/g, " ")
    .replace(/([a-z0-9])([A-Z])/g, "$1 $2")
    .trim()
    .replace(/\S+/g, (word) => word.charAt(0).toUpperCase() + word.slice(1));
}

function toDomId(name: string) {
  return name.replace(/[^A-Za-z0-9_-]/g, "-");
}

function toStringValue(value: unknown) {
  if (value === null || value === undefined) {
    return "";
  }

  if (typeof value === "string") {
    return value;
  }

  return String(value);
}

function formatNumberValue(value: unknown) {
  if (typeof value === "number" && Number.isFinite(value)) {
    return String(value);
  }

  if (typeof value === "string") {
    return value;
  }

  return "";
}

function parseNumberValue(value: string) {
  return value === "" ? null : Number(value);
}

function toBooleanValue(value: unknown) {
  return value === true;
}

function formatJsonValue(value: unknown) {
  if (value === undefined) {
    return "";
  }

  if (typeof value === "string") {
    return value;
  }

  return JSON.stringify(value, null, 2);
}

function parseStructuredValue(event: ChangeEvent<HTMLTextAreaElement>) {
  const { value } = event.target;

  try {
    return JSON.parse(value);
  } catch {
    return value;
  }
}
