# {{title}}

## Summary
- What changed in one to three bullets.
- Mention the user-visible or reviewer-visible outcome.

## Why
- Why this branch exists.
- Why the chosen approach is acceptable.

## Scope
- base: `{{base}}`
- head: `{{head}}`
- changed files: `{{changed_file_count}}`

## Files changed
{{files_changed_bullets}}

## Validation
{{validation_bullets}}

## CI/CD request
```json
{{workflow_inputs_json}}
```

## Risks / review focus
- Call out migrations, schema changes, environment changes, or rollback concerns.
- Point reviewers at the highest-risk files.

## Checklist
- [ ] Lint / tests have been reviewed
- [ ] CI workflow inputs are correct
- [ ] Ready for reviewer attention
