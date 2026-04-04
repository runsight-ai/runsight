export const TEMPLATE_YAML = `\
version: '1.0'
blocks:
  research:
    type: linear
    soul_ref: researcher
  write_summary:
    type: linear
    soul_ref: writer
  quality_review:
    type: gate
    soul_ref: reviewer
    eval_key: write_summary
workflow:
  name: Research & Review
  entry: research
  transitions:
    - from: research
      to: write_summary
    - from: write_summary
      to: quality_review
`;
