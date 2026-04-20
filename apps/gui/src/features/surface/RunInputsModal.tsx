import { useEffect, useMemo, useState } from "react";
import { ApiError } from "@/api/client";
import type { WorkflowInputSchemaItem } from "@runsight/shared/zod";
import { Button } from "@runsight/ui/button";
import {
  Dialog,
  DialogBody,
  DialogContent,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@runsight/ui/dialog";
import { WorkflowInputsForm } from "./WorkflowInputsForm";

type WorkflowInputSchema = Record<string, WorkflowInputSchemaItem>;
type WorkflowInputValues = Record<string, unknown>;
type WorkflowInputErrors = Partial<Record<string, string>>;

interface RunInputsWorkflow {
  name?: unknown;
  input_schema?: unknown;
}

export interface RunInputsModalProps {
  open: boolean;
  workflow: RunInputsWorkflow & Record<string, unknown>;
  initialValues?: WorkflowInputValues;
  submitting?: boolean;
  submitLabel?: string;
  onOpenChange: (open: boolean) => void;
  onSubmit: (inputs: WorkflowInputValues) => Promise<unknown> | unknown;
}

export function RunInputsModal({
  open,
  workflow,
  initialValues,
  submitting = false,
  submitLabel = "Run",
  onOpenChange,
  onSubmit,
}: RunInputsModalProps) {
  const schema = useMemo(
    () => getWorkflowInputSchema(workflow.input_schema),
    [workflow.input_schema],
  );
  const [values, setValues] = useState<WorkflowInputValues>(() =>
    getInitialInputValues(schema, initialValues),
  );
  const [fieldErrors, setFieldErrors] = useState<WorkflowInputErrors>({});
  const [submitError, setSubmitError] = useState<string | null>(null);
  const [internalSubmitting, setInternalSubmitting] = useState(false);
  const isSubmitting = submitting || internalSubmitting;
  const workflowName =
    typeof workflow.name === "string" && workflow.name.trim()
      ? workflow.name.trim()
      : "workflow";

  useEffect(() => {
    if (!open) {
      return;
    }

    setValues(getInitialInputValues(schema, initialValues));
    setFieldErrors({});
    setSubmitError(null);
    setInternalSubmitting(false);
  }, [initialValues, open, schema]);

  function handleOpenChange(nextOpen: boolean) {
    if (!nextOpen && isSubmitting) {
      return;
    }

    onOpenChange(nextOpen);
  }

  function handleCancel() {
    if (isSubmitting) {
      return;
    }

    onOpenChange(false);
  }

  function handleInputChange(name: string, value: unknown) {
    setValues((current) => ({
      ...current,
      [name]: value,
    }));
    setFieldErrors((current) => {
      if (!Object.hasOwn(current, name)) {
        return current;
      }

      const next = { ...current };
      delete next[name];
      return next;
    });
    setSubmitError(null);
  }

  async function handleSubmit() {
    if (isSubmitting) {
      return;
    }

    setFieldErrors({});
    setSubmitError(null);

    const validation = validateInputValues(schema, values);
    if (Object.keys(validation.errors).length > 0) {
      setFieldErrors(validation.errors);
      return;
    }

    setInternalSubmitting(true);
    try {
      await onSubmit(validation.payload);
      await new Promise<void>((resolve) => {
        window.setTimeout(resolve, 10);
      });
      onOpenChange(false);
    } catch (error) {
      const backendErrors = getBackendFieldErrors(error, schema);

      if (Object.keys(backendErrors).length > 0) {
        setFieldErrors(backendErrors);
        return;
      }

      setSubmitError(getSubmitErrorMessage(error));
    } finally {
      setInternalSubmitting(false);
    }
  }

  return (
    <Dialog open={open} onOpenChange={handleOpenChange}>
      <DialogContent size="lg" showCloseButton={!isSubmitting}>
        <DialogHeader>
          <DialogTitle>Run {workflowName}</DialogTitle>
        </DialogHeader>

        <DialogBody className="space-y-4">
          {submitError ? (
            <div
              role="alert"
              className="rounded-md border border-danger-7 bg-danger-3 px-3 py-2 text-sm text-danger-11"
            >
              {submitError}
            </div>
          ) : null}

          <WorkflowInputsForm
            schema={schema}
            values={values}
            errors={fieldErrors}
            submitting={isSubmitting}
            onChange={handleInputChange}
          />
        </DialogBody>

        <DialogFooter>
          <Button variant="ghost" disabled={isSubmitting} onClick={handleCancel}>
            Cancel
          </Button>
          <Button variant="primary" loading={isSubmitting} onClick={handleSubmit}>
            {isSubmitting ? "Running..." : submitLabel}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

function getWorkflowInputSchema(value: unknown): WorkflowInputSchema {
  if (!value || typeof value !== "object" || Array.isArray(value)) {
    return {};
  }

  const schema: WorkflowInputSchema = {};
  for (const [name, item] of Object.entries(value)) {
    if (isWorkflowInputSchemaItem(item)) {
      schema[name] = item;
    }
  }

  return schema;
}

function isWorkflowInputSchemaItem(value: unknown): value is WorkflowInputSchemaItem {
  if (!value || typeof value !== "object" || Array.isArray(value)) {
    return false;
  }

  const type = (value as { type?: unknown }).type;
  return (
    type === "string" ||
    type === "number" ||
    type === "boolean" ||
    type === "json" ||
    type === "array"
  );
}

function getInitialInputValues(
  schema: WorkflowInputSchema,
  initialValues?: WorkflowInputValues,
) {
  const values: WorkflowInputValues = {};

  for (const [name, item] of Object.entries(schema)) {
    if (initialValues && Object.hasOwn(initialValues, name) && initialValues[name] !== undefined) {
      values[name] = initialValues[name];
      continue;
    }

    values[name] = item.sensitive === true ? undefined : item.default;
  }

  return values;
}

function validateInputValues(
  schema: WorkflowInputSchema,
  values: WorkflowInputValues,
): { payload: WorkflowInputValues; errors: WorkflowInputErrors } {
  const payload: WorkflowInputValues = {};
  const errors: WorkflowInputErrors = {};

  for (const [name, item] of Object.entries(schema)) {
    const value = Object.hasOwn(values, name)
      ? values[name]
      : item.sensitive === true
        ? undefined
        : item.default;

    if (item.required === true && isMissingValue(value)) {
      errors[name] = "This field is required.";
      continue;
    }

    if (item.type === "json" || item.type === "array") {
      const structured = normalizeStructuredValue(item.type, value);
      if (!structured.ok) {
        errors[name] = structured.message;
        continue;
      }

      payload[name] = structured.value;
      continue;
    }

    if (item.type === "number") {
      const numberValue = normalizeNumberValue(value);
      if (!numberValue.ok) {
        errors[name] = numberValue.message;
        continue;
      }

      payload[name] = numberValue.value;
      continue;
    }

    payload[name] =
      item.type === "string" && !isMissingValue(value) ? String(value) : value;
  }

  return { payload, errors };
}

function isMissingValue(value: unknown) {
  return (
    value === null ||
    value === undefined ||
    (typeof value === "string" && value.trim() === "")
  );
}

function normalizeStructuredValue(
  type: "json" | "array",
  value: unknown,
):
  | { ok: true; value: unknown }
  | { ok: false; message: string } {
  if (isMissingValue(value)) {
    return { ok: true, value: null };
  }

  let parsed = value;
  if (typeof value === "string") {
    try {
      parsed = JSON.parse(value);
    } catch {
      return {
        ok: false,
        message:
          type === "array"
            ? "Enter a valid JSON array."
            : "Enter valid JSON.",
      };
    }
  }

  if (type === "array" && !Array.isArray(parsed)) {
    return { ok: false, message: "Enter a valid JSON array." };
  }

  return { ok: true, value: parsed };
}

function normalizeNumberValue(
  value: unknown,
):
  | { ok: true; value: number | null }
  | { ok: false; message: string } {
  if (isMissingValue(value)) {
    return { ok: true, value: null };
  }

  const numberValue = typeof value === "number" ? value : Number(value);
  return Number.isFinite(numberValue)
    ? { ok: true, value: numberValue }
    : { ok: false, message: "Enter a valid number." };
}

function getBackendFieldErrors(
  error: unknown,
  schema: WorkflowInputSchema,
): WorkflowInputErrors {
  if (
    !(error instanceof ApiError) ||
    error.code !== "WORKFLOW_INPUT_VALIDATION_ERROR" ||
    !isWorkflowInputValidationDetails(error.details)
  ) {
    return {};
  }

  const errors: WorkflowInputErrors = {};
  for (const fieldError of error.details.fields) {
    if (Object.hasOwn(schema, fieldError.field)) {
      errors[fieldError.field] = fieldError.message;
    }
  }

  return errors;
}

function isWorkflowInputValidationDetails(
  value: unknown,
): value is { fields: Array<{ field: string; message: string }> } {
  if (!value || typeof value !== "object" || Array.isArray(value)) {
    return false;
  }

  const fields = (value as { fields?: unknown }).fields;
  return (
    Array.isArray(fields) &&
    fields.every((field) => {
      if (!field || typeof field !== "object" || Array.isArray(field)) {
        return false;
      }

      const item = field as { field?: unknown; message?: unknown };
      return typeof item.field === "string" && typeof item.message === "string";
    })
  );
}

function getSubmitErrorMessage(error: unknown) {
  return error instanceof Error ? error.message : "Run failed.";
}
