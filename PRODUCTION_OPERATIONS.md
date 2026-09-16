# Production Operations

SDAC uses an exact-commit promotion model. Every change must pass unit, page-render, migration, smoke, release-readiness, and Playwright checks before the same commit enters staging. Production promotion requires the protected `production` GitHub environment.

## Required deployment settings

- `SDAC_STAGING_DEPLOY_HOOK` and `SDAC_PRODUCTION_DEPLOY_HOOK`: public HTTPS deployment endpoints.
- matching rollback hooks: restore the previous known-good immutable build.
- staging and production health URLs ending in `/status?format=json`.
- `SDAC_DEPLOY_TOKEN`: short-lived secret accepted by deployment hooks.

Health verification runs for two minutes. Failure invokes rollback automatically. Database migrations must be backward compatible for one release so the previous application build can run during rollback.

## Service objectives

- dashboard availability: 99.9% monthly
- p95 web response time: under 750 ms
- moderation queue age: under 24 hours
- webhook terminal failure rate: below 1%
- backup recovery point: under 24 hours
- isolated restore recovery time: under 15 minutes

Use Operations Dashboard, public Status, and Recovery Validation to check these objectives. Alerts should fire only when a threshold is crossed or user action is required.
