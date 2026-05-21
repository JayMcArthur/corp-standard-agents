# Resolution Output v1

`.agents/resolution.json` is the primary machine API. Integrations should read it before using tool-specific markdown routers.

It includes workspace identity, matched repo/repo-group, selected profile, applied layers, enabled sources, source trust details, active item ids by kind, inactive recommended items, warnings, active item metadata, and denied items.

Each active item includes provenance, activation reason, activation source, selected profile/pack provenance, trust/review status, privacy, target settings, and body content when safe for the repo class. Denied items and warnings are included with reasons. The machine-readable schema is `docs/specs/v1/resolution-json.schema.json`; public and runtime copies live at `schemas/resolution.schema.json` and `src/team_agents/schemas/resolution-json-v1.schema.json`.
