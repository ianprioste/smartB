# API Documentation

Documentacao dos endpoints ativos no backend atual.

## Base URL

- Backend local: `http://localhost:8000`
- Frontend dev (proxy): `http://localhost:5173/api` (Vite remove `/api` antes de encaminhar)

## Autenticacao

A API usa sessao por cookie `smartb_session`.

Rotas publicas:

- `GET /health`
- `GET /docs`
- `GET /redoc`
- `GET /openapi.json`
- `GET /auth/access/bootstrap-status`
- `POST /auth/access/login`
- `GET /auth/bling/*`

Demais rotas exigem sessao valida.

## Modulos e endpoints

### Auth Bling (`/auth`)

- `GET /auth/bling/connect`
- `POST /auth/bling/connect`
- `GET /auth/bling/callback`
- `GET /auth/bling/status`

### Acesso (`/auth/access`)

- `GET /auth/access/bootstrap-status`
- `POST /auth/access/login`
- `POST /auth/access/logout`
- `GET /auth/access/me`
- `GET /auth/access/profiles`
- `POST /auth/access/profiles`
- `PATCH /auth/access/profiles/{profile_id}`
- `DELETE /auth/access/profiles/{profile_id}`
- `GET /auth/access/users`
- `POST /auth/access/users`
- `PATCH /auth/access/users/{user_id}`
- `DELETE /auth/access/users/{user_id}`

### Configuracao (`/config`)

Modelos:

- `GET /config/models`
- `POST /config/models`
- `GET /config/models/{code}`
- `PUT /config/models/{code}`
- `DELETE /config/models/{code}`

Cores:

- `GET /config/colors`
- `POST /config/colors`
- `GET /config/colors/{code}`
- `PUT /config/colors/{code}`
- `DELETE /config/colors/{code}`

Templates:

- `GET /config/templates`
- `POST /config/templates`
- `GET /config/templates/{template_id}`
- `DELETE /config/templates/{template_id}`

### Produtos Bling (`/bling/products`)

- `GET /bling/products/search`
- `GET /bling/products/list/all`
- `GET /bling/products/{product_id}`

### Planos (`/plans`)

- `POST /plans/new`
- `POST /plans/new-plain`
- `POST /plans/new/save`
- `POST /plans/execute`
- `POST /plans/{plan_id}/execute`
- `POST /plans/recreate-failed-updates`
- `POST /plans/seed-bases`

### Jobs (`/jobs`)

- `GET /jobs`
- `POST /jobs`
- `DELETE /jobs`
- `GET /jobs/{job_id}`
- `GET /jobs/{job_id}/detail`
- `GET /jobs/{job_id}/items`

### Dashboard (`/dashboard`)

- `GET /dashboard/summary`

### Eventos (`/events`)

- `GET /events`
- `POST /events`
- `GET /events/{event_id}`
- `PUT /events/{event_id}`
- `DELETE /events/{event_id}`
- `GET /events/{event_id}/sales`
- `PUT /events/{event_id}/items/{sku}/production`
- `PUT /events/{event_id}/orders/{order_id}/status`

### Pedidos (`/orders`)

- `GET /orders`
- `POST /orders/sync/full`
- `POST /orders/sync/incremental`
- `GET /orders/sync/status`
- `GET /orders/diagnose/{order_numero}`
- `PUT /orders/items/{sku}/production`
- `PUT /orders/orders/{order_id}/status`

## Exemplos

Health check:

```bash
curl http://localhost:8000/health
```

Login:

```bash
curl -X POST http://localhost:8000/auth/access/login \
  -H "Content-Type: application/json" \
  -d '{"email":"admin@local","password":"123456"}'
```

## Referencias

- [ARCHITECTURE.md](./ARCHITECTURE.md)
- [OpenAPI/Swagger](http://localhost:8000/docs)
