# 🔧 WINDOWS SETUP - Celery Workaround

## Problema

No Windows, Celery usa `prefork` por padrão, que causaPermissionError. Corrigimos usando `solo` pool.

## Solução Implementada

1. **Celery App** (`app/workers/celery_app.py`)
   - Detecta se é Windows
   - Usa `solo` pool no Windows (1 processo)
   - Usa `prefork` no Linux/Mac (múltiplos processos)

2. **Worker Script** (`celery_worker_windows.py`)
   - Wrapper Python para executar worker com `--pool=solo`
   - Evita problemas de prefork no Windows

3. **Startup Script** (`start_worker.bat`)
   - Executa via Python wrapper
   - Funciona corretamente no Windows

## Como Usar

### 1. Instale Dependências Primeiro

```bash
cd backend
pip install -r requirements.txt
```

Isso instala:
- celery==5.3.4
- redis==5.0.1
- fastapi==0.104.1
- E todas as outras dependências

### 2. Verifique que Redis está rodando

```bash
docker-compose up -d
```

Verifique com:
```bash
docker-compose ps
```

### 3. Inicie o Server

**Terminal 1:**
```bash
cd backend
python run.py
```

Você verá:
```
INFO:     Uvicorn running on http://127.0.0.1:8000
```

### 4. Inicie o Worker

**Terminal 2:**
```bash
cd backend
python celery_worker_windows.py
```

Você verá:
```
[tasks]

[2026-01-21 XX:XX:XX,XXX: INFO/MainProcess] celery@YOUR-PC ready.
```

## Alternativas

### Opção A: Executar via start scripts

```bash
# Terminal 1
.\start_server.bat

# Terminal 2
.\start_worker.bat
```

### Opção B: Executar com gevent (mais rápido)

Se quiser usar gevent em vez de solo:

```bash
pip install gevent
celery -A app.workers.celery_app worker --pool=gevent --loglevel=info
```

### Opção C: RQ em vez de Celery (mais simples)

Para uma solução mais simples no Windows, considere usar RQ (Redis Queue):

```bash
pip install rq
rq worker
```

## Testando o Worker

### 1. Criar um Job

```bash
curl -X POST http://localhost:8000/jobs \
  -H "Content-Type: application/json" \
  -d '{"type": "sync_products", "input_payload": {}}'
```

### 2. Ver no Worker

Você verá no terminal do worker:
```
[2026-01-21 XX:XX:XX,XXX: INFO/MainProcess] Received task: app.workers.tasks.process_job_task
[2026-01-21 XX:XX:XX,XXX: INFO/spawnpool worker-1] ...job_processing_started...
[2026-01-21 XX:XX:XX,XXX: INFO/spawnpool worker-1] ...job_processing_completed...
```

### 3. Verificar Status

```bash
curl http://localhost:8000/jobs/{job_id}
```

Status mudará de `QUEUED` → `RUNNING` → `DONE`

## Troubleshooting

### Redis Connection Refused

```bash
docker-compose ps  # Verifique se Redis está rodando
docker-compose restart redis
```

### "celery: command not found"

Use Python wrapper em vez de CLI:
```bash
python celery_worker_windows.py
```

### Worker não recebe tarefas

Verifique Redis:
```bash
redis-cli ping
# Deve retornar: PONG
```

### Permissão Negada (PermissionError)

Isso significa que prefork foi usado. Use:
```bash
python celery_worker_windows.py  # Usa solo automaticamente
```

## Próximos Passos

1. ✅ Instale dependências: `pip install -r requirements.txt`
2. ✅ Inicie Redis: `docker-compose up -d`
3. ✅ Teste server: `python run.py`
4. ✅ Teste worker: `python celery_worker_windows.py`
5. 📊 Crie um job e veja o worker processar!

## Notas

- `solo` pool roda tudo em 1 processo (mais lento, mas funciona no Windows)
- `prefork` roda em múltiplos processos (mais rápido, não funciona no Windows)
- Em produção, use Linux/Docker para aproveitar `prefork`
- Para dev no Windows, `solo` é suficiente

---

Se tiver problemas, verifique:
1. Dependências instaladas: `pip list | grep -i celery`
2. Redis rodando: `redis-cli ping`
3. Porta 8000 disponível: `netstat -ano | findstr :8000`
