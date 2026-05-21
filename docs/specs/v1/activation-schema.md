# Activation Schema v1

Optional items are inactive unless a layer or selected profile/job activates them.

Supported activation tables:

- `[skills] enabled`, `disabled`, `recommended`
- `[policies] required`, `enabled`, `disabled`, `recommended`
- `[docs] enabled`, `disabled`, `recommended`
- `[contracts] required`, `enabled`, `disabled`, `recommended`
- `[packs] required`, `enabled`, `disabled`, `recommended`
- `[flows] enabled`, `disabled`, `recommended`
- `[profiles] enabled`, `disabled`, `recommended`

Required policies, contracts, and packs apply automatically and cannot be weakened by later user layers. The machine-readable schema is `schemas/activation.schema.json`.

Pack items may carry their own `[activation]` table. Activating a pack activates its bundled items, records `pack:<pack-id>` provenance on each bundled item, and rejects circular pack references.
