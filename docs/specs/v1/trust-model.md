# trust model v1

Status: Frozen
Date: 2026-05-14

## Purpose

This document freezes the v1 trust model for external sources.

It defines:

- corp-approved source pinning
- optional manifest fingerprint verification
- user-managed trust-on-first-use behavior
- trust store location and record shape
- how trust metadata appears in machine-readable outputs

## Source Registry Entry

Required fields:

- `id`
- `url`
- `commit`
- `namespace`
- `trust_mode`

Optional fields:

- `fingerprint`

Current v1 behavior uses:

- corp-approved sources: pinned commit, optional manifest fingerprint
- user-managed sources: pinned commit plus trust-on-first-use unless a fingerprint is supplied

## Trust Store

TOFU state is stored at:

```text
<cache_root>/trust/sources.json
```

Current v1 record shape per user-managed source:

```json
{
  "url": "...",
  "commit": "...",
  "fingerprint": "...",
  "first_seen_at": "...",
  "last_seen_at": "...",
  "trust_mode": "trust-on-first-use"
}
```

## Verification Rules

### Corp-approved source

- Materialize the source at the exact pinned commit.
- If the checkout head is not the pinned commit, fail.
- If a manifest `fingerprint` is present:
  - compute the checkout fingerprint
  - fail on mismatch
  - emit `trust_status = "verified-manifest-fingerprint"`
- If no manifest fingerprint is present:
  - emit `trust_status = "verified-pinned-commit"`

### User-managed source

- If a manifest `fingerprint` is present, treat it the same as any fingerprinted source.
- Otherwise:
  - on first contact, record URL, commit, and computed fingerprint in the TOFU store
  - emit `trust_status = "recorded-trust-on-first-use"`
  - on later contact:
    - fail if the URL changed
    - fail if the commit stayed the same but the computed fingerprint changed
    - otherwise refresh `commit`, `fingerprint`, and `last_seen_at`
    - emit `trust_status = "verified-trust-on-first-use"`

## Exposed Metadata

Trust metadata must appear in:

- `resolution.json` under `source_details.<source-id>`
- `doctor --json` under `resolution.source_details.<source-id>`

Frozen trust fields:

- `commit`
- `url`
- `fingerprint`
- `fingerprint_mode`
- `trust_status`

## Notes

- This contract is maintained as public reference documentation.
