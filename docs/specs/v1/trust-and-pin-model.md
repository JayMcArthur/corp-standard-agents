# Trust And Pin Model v1

External and personal sources are pinned by commit.

Source manifests include:

- `id`
- `url`
- `commit`
- `namespace`
- `trust_mode`
- optional `fingerprint`

Pinned commits are materialized into the machine cache. Trust-on-first-use records the first seen source metadata in the cache trust store; later mismatches are rejected. Resolution output exposes source commit, fingerprint, fingerprint mode, and trust status.
