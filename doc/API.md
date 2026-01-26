# 📡 API Documentation - smartBling v2

## 🔗 Base URL

```
Development: http://localhost:8000/api
Production: https://smartbling.com.br/api
```

## 🔐 Autenticação

Todos os endpoints (exceto `/auth/login`) requerem bearer token JWT:

```bash
curl -H "Authorization: Bearer YOUR_JWT_TOKEN" \
     https://api.smartbling.com.br/api/endpoint
```

Tokens expiram em 24 horas. Use `/auth/refresh` para renovar.

---

## 🎯 Endpoints Principais

### 📦 Administração

#### 1. Modelos de Impressão

**GET `/admin/models`** - Listar modelos
```json
Response 200:
{
  "data": [
    {
      "id": "uuid",
      "code": "MODELO01",
      "name": "Modelo A4",
      "allowed_sizes": ["P", "M", "G"],
      "size_order": ["P", "M", "G"],
      "is_active": true,
      "created_at": "2024-01-01T10:00:00Z"
    }
  ]
}
```

**POST `/admin/models`** - Criar modelo
```json
Request:
{
  "code": "MODELO02",
  "name": "Modelo A3",
  "allowed_sizes": ["M", "G", "XG"],
  "size_order": ["M", "G", "XG"]
}

Response 201:
{
  "id": "uuid",
  "code": "MODELO02",
  "name": "Modelo A3",
  ...
}

Errors:
- 400: Invalid input
- 409: Code already exists
```

**GET `/admin/models/{code}`** - Obter modelo específico
```json
Response 200:
{
  "id": "uuid",
  "code": "MODELO01",
  "name": "Modelo A4",
  ...
}
```

**PUT `/admin/models/{code}`** - Atualizar modelo
```json
Request:
{
  "name": "Modelo A4 Novo",
  "allowed_sizes": ["P", "M"]
}

Response 200:
{
  "id": "uuid",
  "code": "MODELO01",
  "name": "Modelo A4 Novo",
  ...
}
```

**DELETE `/admin/models/{code}`** - Deletar modelo (soft delete)
```json
Response 204: No content
```

---

#### 2. Cores

**GET `/admin/colors`** - Listar cores
```json
Response 200:
{
  "data": [
    {
      "id": "uuid",
      "code": "BRANCO",
      "name": "Branco",
      "hex_value": "#FFFFFF",
      "is_active": true
    }
  ]
}
```

**POST `/admin/colors`** - Criar cor
```json
Request:
{
  "code": "PRETO",
  "name": "Preto",
  "hex_value": "#000000"
}

Response 201:
{
  "id": "uuid",
  "code": "PRETO",
  "name": "Preto",
  ...
}
```

**PUT `/admin/colors/{code}`** - Atualizar cor
```json
Request:
{
  "name": "Preto Intenso"
}

Response 200:
{...}
```

**DELETE `/admin/colors/{code}`** - Deletar cor
```json
Response 204: No content
```

---

#### 3. Templates

**GET `/admin/templates`** - Listar templates
```json
Response 200:
{
  "data": [
    {
      "id": "uuid",
      "model_code": "MODELO01",
      "kind": "STANDARD",
      "image_url": "https://...",
      "is_active": true
    }
  ]
}
```

**POST `/admin/templates`** - Criar template
```json
Request:
{
  "model_code": "MODELO01",
  "kind": "DIGITAL",
  "image_url": "https://bucket.s3.../template.png"
}

Response 201:
{...}
```

**DELETE `/admin/templates/{id}`** - Deletar template
```json
Response 204: No content
```

---

### 🪄 Wizard (Geração de Planos)

**POST `/wizard/new`** - Criar novo plano via wizard
```json
Request:
{
  "print_type": "DIGITAL",
  "print_width": 20,
  "print_height": 30,
  "models": ["MODELO01", "MODELO02"],
  "colors": ["BRANCO", "PRETO"],
  "quantity_per_size": {
    "P": 100,
    "M": 200
  }
}

Response 200:
{
  "id": "plan-uuid",
  "status": "PENDING",
  "templates": [
    {
      "model": "MODELO01",
      "size": "P",
      "color": "BRANCO",
      "color_code": "1",
      "quantity": 100,
      "image_url": "https://..."
    }
  ],
  "summary": {
    "total_items": 600,
    "unique_templates": 4,
    "total_cost": 1500.00
  }
}

Errors:
- 400: Missing required fields
- 422: Invalid model/color code
- 424: No templates available for selection
```

**GET `/wizard/templates`** - Buscar templates para seleção
```json
Request params:
- model_code: string
- color_code: string (optional)
- size: string (optional)

Response 200:
{
  "data": [
    {
      "template_id": "uuid",
      "model": "MODELO01",
      "color": "BRANCO",
      "image_url": "https://..."
    }
  ]
}
```

---

### 📋 Planos

**GET `/plans`** - Listar planos
```json
Request params:
- status: "PENDING" | "EXECUTING" | "COMPLETED" | "FAILED"
- limit: 10
- offset: 0

Response 200:
{
  "data": [
    {
      "id": "plan-uuid",
      "status": "COMPLETED",
      "created_at": "2024-01-01T10:00:00Z",
      "templates_count": 4,
      "summary": {...}
    }
  ],
  "total": 42,
  "limit": 10,
  "offset": 0
}
```

**GET `/plans/{id}`** - Obter detalhes do plano
```json
Response 200:
{
  "id": "plan-uuid",
  "status": "COMPLETED",
  "templates": [
    {
      "id": "tmpl-uuid",
      "model": "MODELO01",
      "size": "P",
      "color": "BRANCO",
      "quantity": 100,
      "sku": "MODEL01PBR",
      "status": "SUCCESS"
    }
  ],
  "execution": {
    "started_at": "2024-01-01T10:00:00Z",
    "completed_at": "2024-01-01T10:05:00Z",
    "duration_seconds": 300,
    "success_count": 4,
    "error_count": 0
  },
  "summary": {
    "total_items": 600,
    "total_cost": 1500.00,
    "bling_sync": {
      "status": "SYNCED",
      "synced_at": "2024-01-01T10:05:30Z"
    }
  }
}
```

**POST `/plans/{id}/execute`** - Executar plano
```json
Response 200:
{
  "plan_id": "plan-uuid",
  "job_id": "job-uuid",
  "status": "EXECUTING",
  "message": "Plan execution started"
}

Response 409:
{
  "error": "Plan already executed",
  "status": "COMPLETED"
}
```

**GET `/plans/{id}/execution`** - Status de execução
```json
Response 200:
{
  "job_id": "job-uuid",
  "status": "EXECUTING",
  "progress": {
    "processed": 3,
    "total": 4,
    "percentage": 75
  },
  "started_at": "2024-01-01T10:00:00Z",
  "duration_seconds": 45,
  "results": [
    {
      "template_id": "uuid",
      "status": "SUCCESS",
      "sku": "MODEL01PBR",
      "created_at": "2024-01-01T10:01:00Z"
    }
  ]
}
```

**DELETE `/plans/{id}`** - Cancelar/deletar plano
```json
Response 204: No content

Errors:
- 409: Cannot delete executing plan
```

---

### 🔄 Sincronização Bling

**POST `/bling/sync/{plan_id}`** - Sincronizar plano com Bling
```json
Response 200:
{
  "plan_id": "plan-uuid",
  "sync_job_id": "job-uuid",
  "status": "SYNCING",
  "message": "Sync job started"
}

Errors:
- 404: Plan not found
- 409: Plan not executed yet
- 503: Bling API unavailable
```

**GET `/bling/sync/{job_id}`** - Status da sincronização
```json
Response 200:
{
  "job_id": "job-uuid",
  "status": "COMPLETED",
  "synced_items": 4,
  "synced_at": "2024-01-01T10:05:30Z",
  "details": [
    {
      "sku": "MODEL01PBR",
      "bling_id": 12345,
      "price": 150.00,
      "status": "SUCCESS"
    }
  ]
}
```

---

### 👤 Autenticação

**POST `/auth/login`** - Fazer login
```json
Request:
{
  "email": "user@example.com",
  "password": "password123"
}

Response 200:
{
  "access_token": "eyJ0eXAi...",
  "refresh_token": "eyJ0eXAi...",
  "token_type": "bearer",
  "expires_in": 86400
}
```

**POST `/auth/refresh`** - Renovar token
```json
Request:
{
  "refresh_token": "eyJ0eXAi..."
}

Response 200:
{
  "access_token": "eyJ0eXAi...",
  "token_type": "bearer",
  "expires_in": 86400
}
```

**POST `/auth/logout`** - Fazer logout
```json
Response 200:
{
  "message": "Logged out successfully"
}
```

---

### 📊 Relatórios

**GET `/reports/execution`** - Relatório de execução
```json
Request params:
- start_date: "2024-01-01"
- end_date: "2024-01-31"
- status: "SUCCESS" | "FAILED"

Response 200:
{
  "period": {
    "start": "2024-01-01",
    "end": "2024-01-31"
  },
  "summary": {
    "total_plans": 42,
    "successful": 40,
    "failed": 2,
    "success_rate": 95.2,
    "total_items": 8500,
    "total_cost": 21500.00
  },
  "daily": [
    {
      "date": "2024-01-01",
      "plans": 5,
      "items": 1200,
      "cost": 3000.00
    }
  ]
}
```

---

## 🔄 Webhooks

### Plan Execution Status

Enviamos webhook quando plano completa execução:

```json
POST {customer_webhook_url}
Headers:
  X-Webhook-Secret: {webhook_secret}

Body:
{
  "event": "plan.execution.completed",
  "timestamp": "2024-01-01T10:05:00Z",
  "data": {
    "plan_id": "plan-uuid",
    "status": "COMPLETED",
    "success_count": 4,
    "error_count": 0,
    "summary": {...}
  }
}
```

---

## ⚠️ Códigos de Erro

| Code | Mensagem | Descrição |
|------|----------|-----------|
| 400 | Bad Request | Entrada inválida |
| 401 | Unauthorized | Token faltante/inválido |
| 403 | Forbidden | Usuário sem permissão |
| 404 | Not Found | Recurso não encontrado |
| 409 | Conflict | Estado conflitante (ex: plano já executado) |
| 422 | Unprocessable Entity | Dados semanticamente incorretos |
| 429 | Too Many Requests | Rate limit excedido |
| 500 | Internal Server Error | Erro do servidor |
| 503 | Service Unavailable | Bling API indisponível |

---

## 🔒 Rate Limiting

- **Limit**: 300 requisições por minuto por IP
- **Headers de resposta**:
  ```
  X-RateLimit-Limit: 300
  X-RateLimit-Remaining: 299
  X-RateLimit-Reset: 1704110460
  ```
- **Retry-After**: Incluído quando limit excedido

---

## 📝 Exemplos de Uso

### Criar modelo e executar plano

```bash
#!/bin/bash

TOKEN="your_jwt_token"
BASE_URL="http://localhost:8000/api"

# 1. Criar modelo
MODEL=$(curl -X POST "$BASE_URL/admin/models" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "code": "NOVO01",
    "name": "Novo Modelo",
    "allowed_sizes": ["P", "M"],
    "size_order": ["P", "M"]
  }')

echo "Model created: $MODEL"

# 2. Criar plano
PLAN=$(curl -X POST "$BASE_URL/wizard/new" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "print_type": "DIGITAL",
    "models": ["NOVO01"],
    "colors": ["BRANCO"],
    "quantity_per_size": {"P": 100}
  }')

PLAN_ID=$(echo $PLAN | jq -r '.id')
echo "Plan created: $PLAN_ID"

# 3. Executar plano
EXECUTION=$(curl -X POST "$BASE_URL/plans/$PLAN_ID/execute" \
  -H "Authorization: Bearer $TOKEN")

echo "Plan execution started: $EXECUTION"

# 4. Verificar status
for i in {1..30}; do
  STATUS=$(curl -X GET "$BASE_URL/plans/$PLAN_ID/execution" \
    -H "Authorization: Bearer $TOKEN")
  
  PROGRESS=$(echo $STATUS | jq -r '.progress.percentage')
  echo "Progress: $PROGRESS%"
  
  if [ "$PROGRESS" == "100" ]; then
    break
  fi
  
  sleep 1
done
```

---

## 📚 Referências

- [OpenAPI/Swagger](http://localhost:8000/docs) - Documentação interativa
- [ARCHITECTURE.md](./ARCHITECTURE.md) - Arquitetura do sistema
- [TESTING.md](./TESTING.md) - Guia de testes

---

## 🚀 Próximos Passos

1. Adicionar GraphQL alternativo
2. Criar SDK Python/TypeScript
3. Implementar Server-Sent Events (SSE) para updates em tempo real
4. Adicionar versionamento de API (v2, v3)
