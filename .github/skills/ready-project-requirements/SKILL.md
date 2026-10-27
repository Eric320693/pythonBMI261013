---
name: ready-project-requirements
description: 'Inspect GitHub Project #2 Ready items and generate missing User Story and Acceptance Criteria from each work item title. Use when asked to process Ready columns, complete issue requirements, or ensure acceptance criteria use Markdown checklists.'
argument-hint: '[--project-owner <login>] [--project-number <number>] [--ready-status <name>]'
---

# Ready project requirements

Use this skill to complete requirements for work items in the configured GitHub Project.
The default target is user `Eric320693`, Project #2, with status `Ready`.

## Required behavior

- Inspect every project item, including paginated results.
- Process only items whose Status field exactly matches `Ready`.
- Support GitHub Issues and Draft Issues.
- Use the work item title as the only product-context input for generation.
- Add `## User Story` only when that section is missing or empty.
- Add `## Acceptance Criteria` only when that section is missing or empty.
- Render every acceptance criterion as a Markdown checklist item:

  ```markdown
  - [ ] Verifiable condition
  ```

- Never overwrite an existing non-empty User Story or Acceptance Criteria section.
- Stop with an explicit error when GitHub or the AI provider cannot be reached, credentials are missing, or the AI response is invalid.

## Run the bundled implementation

The implementation is in `.github/scripts/update_ready_project_items.py`.
Run it from the repository root:

```powershell
$env:GH_TOKEN = gh auth token
$env:PROJECT_OWNER = "Eric320693"
$env:PROJECT_NUMBER = "2"
$env:READY_STATUS = "Ready"
python .github/scripts/update_ready_project_items.py
```

The script uses an OpenAI-compatible Chat Completions endpoint. Configure:

```powershell
$env:AI_API_KEY = "<provider-api-key>"
$env:AI_API_URL = "https://api.openai.com/v1/chat/completions"
$env:AI_MODEL = "gpt-4o-mini"
```

Do not print or commit API keys. In GitHub Actions, use the repository secrets and variables documented in `README.md`.

## Automated execution

`.github/workflows/update-ready-project-items.yml` runs the same implementation every 15 minutes and supports `workflow_dispatch`.
Use the workflow for unattended updates; use the script directly for a one-time local run or troubleshooting.

Before reporting success, verify that:

1. The command completed without an error.
2. Any updated issue contains both required headings.
3. Every Acceptance Criteria line begins with `- [ ]`.
4. Existing completed sections were not replaced.

## Project reference

Target view: https://github.com/users/Eric320693/projects/2/views/1
