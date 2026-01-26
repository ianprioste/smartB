# 🚀 Deployment Guide - smartBling v2

## 📋 Índice

1. [Desenvolvimento Local](#desenvolvimento-local)
2. [Staging](#staging)
3. [Produção](#produção)
4. [Docker](#docker)
5. [Monitoramento](#monitoramento)
6. [Troubleshooting](#troubleshooting)

---

## 🔧 Desenvolvimento Local

### Prerequisites

- Python 3.10+
- Node.js 18+
- PostgreSQL 14+
- Redis 7+
- Docker & Docker Compose (opcional)

### Setup Inicial

```bash
# 1. Clonar repositório
git clone https://github.com/seu-org/smartbling.git
cd smartbling

# 2. Criar arquivo .env.local
cp .env.example .env.local
# Editar .env.local com valores locais

# 3. Backend setup
cd backend
python -m venv venv

# Windows
venv\Scripts\activate
# macOS/Linux
source venv/bin/activate

pip install -r requirements.txt
python -m alembic upgrade head

# 4. Frontend setup
cd ../frontend
npm install
npm run dev

# 5. Rodar tudo junto
cd ..
docker-compose -f docker-compose.dev.yml up
```

### Variáveis de Ambiente (.env.local)

```env
# Backend
ENVIRONMENT=development
DEBUG=true
LOG_LEVEL=DEBUG
SECRET_KEY=your-secret-key-for-dev

# Database
DATABASE_URL=postgresql://postgres:postgres@localhost:5432/smartbling_dev
REDIS_URL=redis://localhost:6379/0

# Bling
BLING_CLIENT_ID=your_bling_client_id
BLING_CLIENT_SECRET=your_bling_client_secret
BLING_API_URL=https://api.bling.com.br

# OAuth
OAUTH_CLIENT_ID=local
OAUTH_CLIENT_SECRET=local-secret
OAUTH_REDIRECT_URI=http://localhost:3000/auth/callback

# Frontend
VITE_API_URL=http://localhost:8000/api
VITE_ENV=development
```

### Rodar Locally com Docker

```bash
# Apenas banco de dados
docker-compose -f docker-compose.dev.yml up postgres redis

# Aplicação completa
docker-compose -f docker-compose.dev.yml up

# Com hot-reload
docker-compose -f docker-compose.dev.yml up --watch
```

---

## 🏢 Staging

Ambiente para testes pré-produção com dados reais.

### Deploy para Staging

```bash
# 1. Build das imagens
docker build -t smartbling:staging-backend ./backend
docker build -t smartbling:staging-frontend ./frontend

# 2. Push para registry (AWS ECR, Docker Hub, etc.)
docker tag smartbling:staging-backend 123456789.dkr.ecr.us-east-1.amazonaws.com/smartbling:staging-backend
docker push 123456789.dkr.ecr.us-east-1.amazonaws.com/smartbling:staging-backend

# 3. Deploy (exemplo com AWS ECS)
aws ecs update-service \
  --cluster smartbling-staging \
  --service smartbling-backend \
  --force-new-deployment

# 4. Verificar health
curl https://staging.smartbling.com.br/api/health
```

### Configurações Staging

```yaml
# docker-compose.staging.yml
version: '3.8'

services:
  backend:
    image: smartbling:staging-backend
    environment:
      ENVIRONMENT: staging
      DEBUG: false
      LOG_LEVEL: INFO
      DATABASE_URL: ${DATABASE_URL}
      REDIS_URL: ${REDIS_URL}
    ports:
      - "8000:8000"
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8000/api/health"]
      interval: 30s
      timeout: 10s
      retries: 3

  frontend:
    image: smartbling:staging-frontend
    environment:
      VITE_API_URL: https://staging.smartbling.com.br/api
      VITE_ENV: staging
    ports:
      - "3000:3000"

  postgres:
    image: postgres:15
    volumes:
      - staging-db:/var/lib/postgresql/data
    environment:
      POSTGRES_PASSWORD: ${DB_PASSWORD}

  redis:
    image: redis:7

volumes:
  staging-db:
```

### Checklist Pré-Deploy Staging

- [ ] Testes locais passando
- [ ] Migrations testadas
- [ ] Variáveis de ambiente configuradas
- [ ] Secrets seguros (sem hardcoding)
- [ ] Database backup antes de deploy
- [ ] Documentação atualizada

---

## 🌍 Produção

### Recomendações

**Infraestrutura:**
- AWS ECS/Kubernetes para orquestração
- RDS PostgreSQL com Multi-AZ e backups automáticos
- ElastiCache Redis com failover
- CloudFront para static assets
- S3 para uploads (templates, imagens)
- CloudWatch para logs e monitoramento

### Pre-Production Checklist

```
SEGURANÇA
- [ ] JWT_SECRET único e forte (min 32 chars)
- [ ] CORS configurado corretamente
- [ ] Rate limiting ativo (300 req/min)
- [ ] SQL injection prevention (SQLAlchemy parametrized)
- [ ] CSRF tokens em forms
- [ ] HTTPS obrigatório
- [ ] Secrets Manager para credenciais
- [ ] VPC segura sem acesso público desnecessário

PERFORMANCE
- [ ] Cache Redis configurado
- [ ] Database connection pooling
- [ ] Nginx/CloudFront caching
- [ ] CDN para static assets
- [ ] Database indexes criados
- [ ] Slow query logging ativo

INFRAESTRUTURA
- [ ] Load balancer configurado
- [ ] Auto-scaling rules
- [ ] SSL/TLS certificado válido
- [ ] Domain DNS apontando correto
- [ ] Health checks funcionando
- [ ] Logs centralizados
- [ ] Backups automáticos enabled
- [ ] VPC/Security groups corretos

DADOS
- [ ] Database backup antes de deploy
- [ ] Migration tested on production-like environment
- [ ] Data retention policies
- [ ] GDPR compliance (se aplicável)
- [ ] Secrets não em logs

MONITORAMENTO
- [ ] CloudWatch dashboards
- [ ] Alertas configurados
- [ ] Error tracking (Sentry)
- [ ] APM (Application Performance Monitoring)
- [ ] Log aggregation (ELK, CloudWatch)
- [ ] Uptime monitoring
```

### Deploy Script (AWS ECS)

```bash
#!/bin/bash
set -e

ENVIRONMENT="production"
REGION="us-east-1"
CLUSTER="smartbling-prod"

echo "🚀 Deploying smartBling to $ENVIRONMENT..."

# 1. Build e push das imagens
echo "📦 Building Docker images..."
docker build \
  --build-arg ENVIRONMENT=$ENVIRONMENT \
  -t smartbling:prod-backend-$(date +%s) \
  ./backend

docker build \
  --build-arg ENVIRONMENT=$ENVIRONMENT \
  -t smartbling:prod-frontend-$(date +%s) \
  ./frontend

# 2. Push para ECR
echo "📤 Pushing to ECR..."
aws ecr get-login-password --region $REGION | \
  docker login --username AWS --password-stdin \
  123456789.dkr.ecr.$REGION.amazonaws.com

docker push 123456789.dkr.ecr.$REGION.amazonaws.com/smartbling:prod-backend-*
docker push 123456789.dkr.ecr.$REGION.amazonaws.com/smartbling:prod-frontend-*

# 3. Migrations (se necessário)
echo "🔄 Running migrations..."
aws ecs run-task \
  --cluster $CLUSTER \
  --task-definition smartbling-migrate \
  --launch-type FARGATE \
  --network-configuration "awsvpcConfiguration={subnets=[subnet-xxx],securityGroups=[sg-xxx]}"

# Esperar migrations completar
sleep 30

# 4. Update services
echo "🔄 Updating ECS services..."
aws ecs update-service \
  --cluster $CLUSTER \
  --service smartbling-backend \
  --force-new-deployment

aws ecs update-service \
  --cluster $CLUSTER \
  --service smartbling-frontend \
  --force-new-deployment

# 5. Verificar health
echo "✅ Waiting for services to be healthy..."
for i in {1..30}; do
  STATUS=$(curl -s -o /dev/null -w "%{http_code}" \
    https://smartbling.com.br/api/health)
  
  if [ $STATUS -eq 200 ]; then
    echo "✅ Services are healthy!"
    break
  fi
  
  echo "⏳ Health check: $STATUS (attempt $i/30)"
  sleep 10
done

if [ $STATUS -ne 200 ]; then
  echo "❌ Deploy failed - services not healthy"
  exit 1
fi

echo "🎉 Deploy completed successfully!"
```

---

## 🐳 Docker

### Dockerfile Backend

```dockerfile
# backend/Dockerfile
FROM python:3.10-slim as builder

WORKDIR /build
RUN apt-get update && apt-get install -y \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --user --no-cache-dir -r requirements.txt

# Runtime stage
FROM python:3.10-slim

WORKDIR /app

RUN apt-get update && apt-get install -y \
    postgresql-client \
    && rm -rf /var/lib/apt/lists/*

COPY --from=builder /root/.local /root/.local
ENV PATH=/root/.local/bin:$PATH

COPY . .

ARG ENVIRONMENT=production
ENV ENVIRONMENT=$ENVIRONMENT

EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
  CMD curl -f http://localhost:8000/api/health || exit 1

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

### Dockerfile Frontend

```dockerfile
# frontend/Dockerfile
FROM node:18-alpine as builder

WORKDIR /build

COPY package*.json ./
RUN npm ci

COPY . .

ARG VITE_ENV=production
ENV VITE_ENV=$VITE_ENV
ENV VITE_API_URL=https://api.smartbling.com.br

RUN npm run build

# Nginx stage
FROM nginx:alpine

COPY --from=builder /build/dist /usr/share/nginx/html
COPY nginx.conf /etc/nginx/nginx.conf

EXPOSE 80

HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
  CMD wget --quiet --tries=1 --spider http://localhost/ || exit 1

CMD ["nginx", "-g", "daemon off;"]
```

### docker-compose.prod.yml

```yaml
version: '3.8'

services:
  backend:
    image: smartbling:prod-backend
    restart: always
    environment:
      ENVIRONMENT: production
      DEBUG: false
      LOG_LEVEL: INFO
      DATABASE_URL: postgresql://${DB_USER}:${DB_PASSWORD}@postgres:5432/smartbling
      REDIS_URL: redis://redis:6379/0
    depends_on:
      postgres:
        condition: service_healthy
      redis:
        condition: service_healthy
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8000/api/health"]
      interval: 30s
      timeout: 10s
      retries: 3
    networks:
      - smartbling-net
    logging:
      driver: "awslogs"
      options:
        awslogs-group: "/ecs/smartbling-backend"
        awslogs-region: "us-east-1"
        awslogs-stream-prefix: "ecs"

  frontend:
    image: smartbling:prod-frontend
    restart: always
    ports:
      - "80:80"
    depends_on:
      - backend
    networks:
      - smartbling-net

  postgres:
    image: postgres:15
    restart: always
    environment:
      POSTGRES_USER: ${DB_USER}
      POSTGRES_PASSWORD: ${DB_PASSWORD}
      POSTGRES_DB: smartbling
    volumes:
      - postgres-data:/var/lib/postgresql/data
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U ${DB_USER}"]
      interval: 10s
      timeout: 5s
      retries: 5

  redis:
    image: redis:7-alpine
    restart: always
    healthcheck:
      test: ["CMD", "redis-cli", "ping"]
      interval: 10s
      timeout: 5s
      retries: 5
    volumes:
      - redis-data:/data

volumes:
  postgres-data:
  redis-data:

networks:
  smartbling-net:
    driver: bridge
```

---

## 📊 Monitoramento

### Health Checks

```python
# backend/app/api/health.py
@router.get("/health")
async def health_check(db: Session = Depends(get_db)):
    """Health check endpoint."""
    try:
        # Database check
        db.execute("SELECT 1")
        
        # Redis check
        redis_client.ping()
        
        return {
            "status": "healthy",
            "timestamp": datetime.utcnow().isoformat(),
            "version": "2.0.0",
        }
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        raise HTTPException(status_code=503, detail="Service unavailable")
```

### CloudWatch Logs

```bash
# Visualizar logs
aws logs tail /ecs/smartbling-backend --follow

# Buscar erros
aws logs filter-log-events \
  --log-group-name /ecs/smartbling-backend \
  --filter-pattern "ERROR"
```

### Métricas Importantes

```
Application:
- Requisições por minuto (RPM)
- Latência média (p50, p95, p99)
- Taxa de erro (4xx, 5xx)
- Planos executados por dia
- Sincronizações Bling bem-sucedidas

Infrastructure:
- CPU usage (target: <70%)
- Memory usage (target: <80%)
- Disk space
- Database connections
- Redis memory

Business:
- Total items processados
- Receita diária
- Taxa de sucesso de execução
- Feedback de clientes
```

### Alertas Recomendados

```
Critical:
- HTTP 5xx > 5 em 1 minuto
- Latência p99 > 2s
- Database connection pool exhausted
- Redis reachable: NO
- Disk space < 10%

Warning:
- HTTP 4xx > 20 em 5 minutos
- Latência p95 > 1s
- CPU usage > 80%
- Memory > 85%
- Database slow queries > 5 em 1 min
```

---

## 🔍 Troubleshooting

### Problema: API retorna 503

```bash
# 1. Verificar health
curl http://localhost:8000/api/health

# 2. Verificar logs
docker logs smartbling-backend

# 3. Verificar database
docker exec smartbling-postgres psql -U postgres -d smartbling -c "SELECT COUNT(*) FROM users;"

# 4. Verificar Redis
docker exec smartbling-redis redis-cli ping
```

### Problema: Frontend mostra erro de conexão

```bash
# 1. Verificar CORS
curl -H "Origin: http://localhost:3000" \
     -H "Access-Control-Request-Method: POST" \
     http://localhost:8000/api/health

# 2. Verificar API URL no frontend
console.log(import.meta.env.VITE_API_URL)

# 3. Verificar network tab no DevTools
```

### Problema: Database migrations falhando

```bash
# 1. Verificar status
python -m alembic current

# 2. Verificar histórico
python -m alembic history

# 3. Downgrade (se necessário)
python -m alembic downgrade -1

# 4. Upgrade novamente
python -m alembic upgrade head

# 5. Verificar logs
python -m alembic upgrade head --sql  # Ver SQL que será executado
```

### Problema: Plano fica preso em EXECUTING

```bash
# 1. Verificar job status em Redis
redis-cli keys "job:*"
redis-cli get "job:job-uuid"

# 2. Limpar job stuck
redis-cli del "job:job-uuid"

# 3. Marcar plano como falho
UPDATE plans SET status = 'FAILED' WHERE id = 'plan-uuid';

# 4. Checar logs do Celery
docker logs smartbling-worker
```

---

## 📞 Support

- 📧 Email: support@smartbling.com.br
- 💬 Slack: #smartbling-incidents
- 🐛 Bugs: [GitHub Issues](https://github.com/seu-org/smartbling/issues)
- 📖 Docs: [smartbling.com.br/docs](https://smartbling.com.br/docs)

---

## 📚 Referências

- [ARCHITECTURE.md](./ARCHITECTURE.md) - Arquitetura do sistema
- [API.md](./API.md) - Documentação de API
- [TESTING.md](./TESTING.md) - Guia de testes
- [AWS ECS Documentation](https://docs.aws.amazon.com/ecs/)
