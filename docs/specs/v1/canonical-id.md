# Canonical Id v1

Canonical ids identify the source, namespace, item kind, and slug.

Format:

```text
(corp|external|user).<namespace>.(skill|policy|doc|contract|flow|pack|profile).<slug>
```

`namespace` and `slug` must start with a lowercase alphanumeric character and may contain lowercase alphanumerics, `_`, and `-`.

Kinds must match the folder and `item.toml` `kind` field.
