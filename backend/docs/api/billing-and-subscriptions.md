# Billing & Subscriptions API

ComicStudio AI Phase 6 introduces credit-based billing, subscription plans, payments, and audit logging.

## Authentication

All endpoints (except payment webhook) require `Authorization: Bearer <JWT>` header.

## Credit Billing

### Get Balance
`GET /api/billing/balance`

Response:
```json
{
  "code": 0,
  "message": "success",
  "data": { "user_id": "...", "credits": 95, "plan": "free" }
}
```

### List Transactions
`GET /api/billing/transactions?page=1&page_size=20`

Response:
```json
{
  "code": 0,
  "data": {
    "items": [
      {
        "id": "...",
        "user_id": "...",
        "type": "consumption",
        "amount": -10,
        "balance_after": 90,
        "reason": "text2img",
        "description": "AI operation: text2img",
        "created_at": "2026-07-19T..."
      }
    ],
    "total": 42,
    "page": 1,
    "page_size": 20
  }
}
```

## Subscriptions

### List Plans
`GET /api/subscriptions/plans`

Returns the three plans (free, pro, enterprise) with price, credits, and rate limit info.

### Get Current Subscription
`GET /api/subscriptions/current`

### Subscribe
`POST /api/subscriptions/subscribe`
```json
{ "plan": "pro", "duration_days": 30, "auto_renew": true, "payment_method": "stripe" }
```

### Cancel
`POST /api/subscriptions/cancel`

## Payments

### Create Payment Intent
`POST /api/payments/intent`
```json
{ "plan": "pro", "duration_days": 30, "auto_renew": true }
```
Response includes `client_secret` for Stripe.js frontend integration.

### Confirm Payment
`POST /api/payments/confirm`
```json
{ "intent_id": "pi_xxx" }
```

### Webhook
`POST /api/payments/webhook`
Stripe webhook events. No auth — verified by signature header.

## Admin

All admin endpoints require `role == "admin"`.

- `GET /api/admin/stats` — system statistics
- `GET /api/admin/users?page=1&page_size=20` — list users
- `POST /api/admin/users/{id}/ban` — ban user
- `POST /api/admin/users/{id}/unban` — unban user
- `POST /api/admin/users/{id}/credits` — grant credits `{ "amount": 1000, "reason": "..." }`
- `POST /api/admin/users/{id}/promote-admin` — promote to admin
- `POST /api/admin/users/{id}/demote-admin` — demote to user
- `GET /api/admin/audit-logs?page=1&page_size=50` — audit log query

## Credit Costs

| AI Operation | Endpoint | Credits |
|--------------|----------|---------|
| text2img | POST /api/ai/text2img | 10 |
| tts | POST /api/ai/tts | 5 |
| chat | POST /api/ai/chat | 1 |
| video_compose | POST /api/ai/video/compose | 50 |
| character_generate | POST /api/ai/character/generate | 30 |

Insufficient credits return HTTP 402 (Payment Required) with message `积分不足`. Failed AI operations automatically refund credits.

## Rate Limiting

Rate limits per plan (requests per minute):

| Plan | Limit |
|------|-------|
| free | 30 |
| pro | 120 |
| enterprise | 600 |

When exceeded, HTTP 429 with `Retry-After` header. Disabled in desktop mode or when Redis is not configured.
