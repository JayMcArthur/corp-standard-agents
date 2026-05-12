# Release Checklist

## Before Tagging

- Run `PYTHONPATH=src python3 -m unittest discover -s tests -v`
- Run `bash scripts/check_example_flow.sh`
- Run `team-agents doctor --workspace <example-workspace>`
- Review generated output behavior for:
  - internal tracked `AGENTS.md`
  - client tracked `AGENTS.md`
  - client repo `corp-private` exclusion
- Confirm source cache and trust metadata behavior still matches the requirements

## Publication Hygiene

- Verify `LICENSE`, `README.md`, `CONTRIBUTING.md`, and `SECURITY.md` are present
- Verify the license text and README wording both still reflect the intended source-available/public-preview posture
- Verify `.gitignore` excludes local caches, virtualenvs, and generated artifacts
- Verify no local `.tmp/`, `__pycache__/`, `.egg-info/`, or generated `.agents/` content is staged

## After Publishing

- Create the first issues for packaging polish, adapter support, and richer trust workflows
