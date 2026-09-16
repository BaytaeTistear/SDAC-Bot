# API and Webhooks

The canonical OpenAPI 3.1 document is `/api/v1/openapi.json`; human-readable documentation is `/api/docs`. Public endpoints return only approved records belonging to servers that explicitly enable the public gallery. `limit` is bounded to 1–100.

Webhook deliveries contain an event ID, event name, server ID, creation timestamp, and minimal record identity/status data. Verify `X-SDAC-Signature-256` as HMAC-SHA256 over the exact raw body. Deduplicate with `Idempotency-Key`.

Deliveries use a durable outbox and bounded exponential retries. An endpoint is disabled after ten consecutive failures. Operators can inspect failures in Operations Dashboard, rotate secrets by replacing the subscription, and replay dead events after correcting the endpoint.
