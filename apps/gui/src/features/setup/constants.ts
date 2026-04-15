export const TEMPLATE_YAML = `\
version: '1.0'
id: research-review
kind: workflow
tools:
  - file_io
# REQUIRED BEFORE RUNNING:
# - Replace every PLACEHOLDER_PROVIDER_ID with one of your configured provider ids.
# - Replace every PLACEHOLDER_MODEL_NAME with a model that belongs to that provider.
# - Temperature defaults to 1 below. If your chosen model does not support temperature,
#   remove the temperature line for that soul.
souls:
  researcher:
    id: researcher
    kind: soul
    name: Researcher
    role: Research File Writer
    system_prompt: >
      You are a fast research assistant.
      Use the user's task as the topic. If the task is blank or too generic,
      default to "Runsight onboarding starter workflow".
      Produce a concise markdown research note with a title, 3 to 5 concrete bullets,
      and a short "Next steps" section.
      If previous_round_context appears in the provided context, use it to improve the draft.
      Before finishing, you MUST call the file_io tool to write the markdown to
      custom/outputs/onboarding-research-brief.md.
      After the tool call succeeds, return the same markdown.
    tools:
      - file_io
    required_tool_calls:
      - file_io
    max_tool_iterations: 4
    provider: PLACEHOLDER_PROVIDER_ID
    model_name: PLACEHOLDER_MODEL_NAME
    temperature: 1
    avatar_color: info
  reviewer:
    id: reviewer
    kind: soul
    name: Reviewer
    role: Quality Gate Reviewer
    system_prompt: >
      Review the draft research note.
      Return PASS if it is specific, structured, and actionable.
      Return FAIL: followed by one short paragraph of concrete fixes if it is too vague,
      generic, or missing the required structure.
    max_tool_iterations: 3
    provider: PLACEHOLDER_PROVIDER_ID
    model_name: PLACEHOLDER_MODEL_NAME
    temperature: 1
    avatar_color: accent
  error_writer:
    id: error_writer
    kind: soul
    name: Error Writer
    role: Error Stub Writer
    system_prompt: >
      This block only runs after the review flow fails or errors.
      Write a short markdown stub to custom/outputs/onboarding-research-error.md.
      The stub should explain that the workflow did not produce a verified report yet
      and that the operator should inspect the latest run details.
      Before finishing, you MUST call the file_io tool to write the stub file.
      After the tool call succeeds, return one sentence with the file path.
    tools:
      - file_io
    required_tool_calls:
      - file_io
    max_tool_iterations: 3
    provider: PLACEHOLDER_PROVIDER_ID
    model_name: PLACEHOLDER_MODEL_NAME
    temperature: 1
    avatar_color: warning
blocks:
  draft_report:
    type: linear
    soul_ref: researcher
  quality_gate:
    type: gate
    soul_ref: reviewer
    eval_key: draft_report
  review_loop:
    type: loop
    inner_block_refs:
      - draft_report
      - quality_gate
    max_rounds: 2
    break_on_exit: pass
    retry_on_exit: fail
    carry_context:
      enabled: true
      mode: all
      source_blocks:
        - draft_report
        - quality_gate
      inject_as: previous_round_context
    error_route: write_error_stub
  check_review_status:
    type: code
    timeout_seconds: 10
    code: |
      def main(data):
          loop_meta = data["shared_memory"].get("__loop__review_loop", {}) or {}
          break_reason = str(loop_meta.get("break_reason", ""))
          passed = "pass" in break_reason
          return {
              "status": "pass" if passed else "fail",
              "break_reason": break_reason,
              "exit_handle": "pass" if passed else "fail",
          }
  write_error_stub:
    type: linear
    soul_ref: error_writer
  finish:
    type: code
    timeout_seconds: 10
    code: |
      import json

      def _normalize(raw):
          if isinstance(raw, dict):
              return raw
          if isinstance(raw, str):
              try:
                  return json.loads(raw)
              except Exception:
                  return {"raw": raw}
          return {"raw": raw}

      def main(data):
          return {
              "status": "completed",
              "report_path": "custom/outputs/onboarding-research-brief.md",
              "error_stub_path": "custom/outputs/onboarding-research-error.md",
              "review_status": _normalize(data["results"].get("check_review_status", "")),
              "error_stub": _normalize(data["results"].get("write_error_stub", "")),
          }
workflow:
  name: Research & Review
  entry: review_loop
  transitions:
    - from: review_loop
      to: check_review_status
    - from: write_error_stub
      to: finish
  conditional_transitions:
    - from: check_review_status
      pass: finish
      fail: write_error_stub
      default: write_error_stub
`;

export function buildTemplateWorkflowYaml(workflowId: string): string {
  return TEMPLATE_YAML.replace(/^id: research-review$/m, `id: ${workflowId}`);
}
