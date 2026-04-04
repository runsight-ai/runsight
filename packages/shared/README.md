# packages/shared

Canonical home for contracts shared between `apps/api` and `apps/gui`.

Examples:

- zod schemas
- generated OpenAPI types
- DTOs
- shared enums

Operational notes:

- Generate contracts from here with `pnpm -C packages/shared run generate:types`.
- Validate freshness with `pnpm -C packages/shared run check:types-fresh`.

This package should stay contract-only.
