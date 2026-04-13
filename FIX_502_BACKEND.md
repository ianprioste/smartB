# Fix para Erro 502 - Backend não respondendo (Login e Reset de Senha)

## Problema

O backend está retornando **502 Bad Gateway** para os endpoints de autenticação:
- `/auth/access/login`
- `/auth/access/forgot-password/request`
- `/auth/access/bootstrap-status`
- `/auth/access/me`

## Causa Raiz

A migration `011_order_tags_and_links.py` não foi commitada no repositório e havia um bug na definição do tipo UUID que causava erro ao executar no SQLite.

Com o deploy anterior do feature de tags, o banco esperava as tabelas `order_tags` e `order_tag_links`, mas elas não existiam.

## Solução

### 1. No Host - Fazer Pull da Correção

```bash
cd /opt/smartB  # ou o caminho do seu projeto
git pull origin main
```

Você deve ver:
```
dcc8139 fix(migration): fix UUID type handling in alembic migration 011 for SQLite compatibility
```

### 2. Aplicar a Migration

```bash
# Ativar ambiente Python
source .venv/bin/activate  # ou seu método de ativação

# Entrar no diretório backend
cd backend

# Aplicar a migration
alembic upgrade head
```

**Saída esperada:**
```
INFO  [alembic.runtime.migration] Context impl SQLiteImpl.
INFO  [alembic.runtime.migration] Will assume non-transactional DDL.
INFO  [alembic.runtime.migration] Running upgrade 010_password_reset_codes -> 011_order_tags_and_links, Add order tags tables
```

Se receber erro `"The user 'postgres' does not have access to server"` em PostgreSQL, executar com credenciais:
```bash
DATABASE_URL="postgresql://user:password@localhost/smartbling" alembic upgrade head
```

### 3. Reiniciar o Backend

```bash
# Se usando systemd:
sudo systemctl restart smartbling-backend

# Se usando Docker:
docker restart smartbling-backend

# Se rodando manual:
# Ctrl+C para parar e depois:
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000
```

### 4. Validar a Correção

Casa a correção tenha funcionado, os endpoints de auth devem retornar **não erros 502**:

```bash
# Teste local (deve retornar 400 ou 401, não 502):
curl -X POST http://localhost:8000/api/auth/access/login \
  -H "Content-Type: application/json" \
  -d '{"email":"test@test.com","password":"test"}'

# Deve retornar algo como:
# {"detail":"E-mail ou senha incorretos"}
# OU 200 se credenciais corretas
```

No browser, você deve conseguir acessar `/login` sem erros 502.

## O que foi corrigido

### Arquivo: `backend/alembic/versions/011_order_tags_and_links.py`

**Antes (quebrado):**
```python
from sqlalchemy.dialects.postgresql import UUID

def upgrade() -> None:
    uuid_type = UUID(as_uuid=True) if ... else sa.CHAR(...)  # ❌ UUID é do PostgreSQL
```

**Depois (corrigido):**
```python
from sqlalchemy.dialects.postgresql import UUID as PG_UUID

def upgrade() -> None:
    uuid_type = PG_UUID(as_uuid=True) if ... else sa.CHAR(...)  # ✅ PG_UUID só usado no PostgreSQL
```

O problema era que `UUID` era importado como sendo PostgreSQL-específico, e mesmo no ramo `else` (SQLite) ele tinha referências erradas do PostgreSQL.

## Próximos passos

1. Verificar nos logs se há outros erros
2. Executar smoke tests de login e reset de senha
3. Monitorar o backend nos próximos minutos

## Logs para Debug (se necessário)

```bash
# Verificar logs do backend:
sudo journalctl -u smartbling-backend -f -n 100

# Se Docker:
docker logs -f smartbling-backend --tail 100

# Se manual, os logs devem aparecer no terminal
```

## Rollback (em caso de problema)

Se a migration causar mais problemas, pode fazer rollback:

```bash
cd backend
alembic downgrade -1  # volta para a migration anterior
```

Depois reiniciar o backend.
