# ⚡ Plano de Ação: Reduzir Requisições Bling

## Problema

Você está vendo muitas requisições ao Bling quando filtra um evento.

---

## Passo 1: Diagnosticar (5 minutos)

### Execute o script de diagnóstico:

```bash
cd backend
python run.py  # em outro terminal
```

Em outro terminal:
```bash
cd backend
python diagnose_requests.py
```

### Você verá algo assim:

**Cenário Pessimista** (o que provavelmente está acontecendo):
```
Total orders in period: 42
Orders with items in list (Phase 1): 0
Orders without items (Phase 2): 42

API Calls:
   Phase 1 (list): 1 call
   Phase 2 (detail): 42 calls
   Total: 43 calls

⚠️  WARNING: 42 detail fetches!
     This might be slow depending on Bling rate limit
```

**Cenário Ideal**:
```
Total orders in period: 42
Orders with items in list (Phase 1): 42
Orders without items (Phase 2): 0

API Calls:
   Phase 1 (list): 1 call
   Total: 1 call

✅ OPTIMAL: All items in list!
```

---

## Passo 2: Identificar a Causa

### A. Se vir "0 items in list" e "42 without items":

**Causa:** O `/pedidos/vendas` do Bling NÃO retorna o campo `itens`

**Prova:** Todas as requests vão para Phase 2

### B. Se vir "42 items in list" e "0 without items":

**Causa:** Sistema está funcionando corretamente

**Status:** Nenhum problema

### C. Se vir "20 with items, 22 without":

**Causa:** Parcial - alguns pedidos têm items, outros não

**Status:** Aceitável, mas pode otimizar

---

## Passo 3: Solução Rápida (Implementar Agora)

Se viu que **maioria dos pedidos não tem items na lista**, vou implementar **caching local**.

### Como Funciona:

1. **Primeira execução:** Busca todos os detalhes (lento: ~30-40s para 100 pedidos)
2. **Próximas execuções:** Usa cache local (rápido: <100ms)

### Vantagem:
- Respeita rate limit do Bling
- Sem timeout
- Progressivamente mais rápido

### Como Ativar:

Eu vou criar uma tabela para cache:
```sql
CREATE TABLE order_cache (
  id INTEGER PRIMARY KEY,
  numero VARCHAR,
  data TIMESTAMP,
  items JSONB,
  cached_at TIMESTAMP,
  ttl INTEGER  -- Time to live: 24h
)
```

E modificar o código:
```python
# Em events.py, Phase 2:
cached_detail = get_cached_order(order_id)
if cached_detail:
    detail = cached_detail  # Usa cache
else:
    detail = await client.get(f"/pedidos/vendas/{order_id}")  # Busca Bling
    cache_order(order_id, detail)  # Salva cache
```

---

## Passo 4: Métricas Esperadas

### Sem Cache (Atual):
```
1º acesso: 43 calls = 30-40 segundos
2º acesso: 43 calls = 30-40 segundos
3º acesso: 43 calls = 30-40 segundos
```

### Com Cache (Proposto):
```
1º acesso: 43 calls = 30-40 segundos (mesmo, sem cache ainda)
2º acesso: 1 call = <100ms (usa cache!)
3º acesso: 1 call = <100ms (usa cache!)
4º acesso: 1 call = <100ms (usa cache!)
```

**Melhoria:** 40x mais rápido após primeira execução

---

## Próximos Passos

### Você:

1. Execute:
   ```bash
   cd backend
   python run.py
   cd backend && python diagnose_requests.py
   ```

2. Mande resultado:
   ```
   Total orders: X
   With items in list: Y
   Without items: Z
   Total API calls: A
   ```

3. Diga se está lento

### Eu:

Com essas informações, vou:

1. ✅ Implementar cache local
2. ✅ Adicionar logs para rastrear uso de cache
3. ✅ Testes para validar performance
4. ✅ Documentacao atualizada

---

## Alternativa: Sem Cache (Mais Simples)

Se NÃO quiser cache, posso:

1. **Reduzir sem limite**, esperar mais tempo (30-40s é aceitável?)
2. **Dividir em janelas** (buscar 1 semana por vez, reduz número de calls)
3. **Aumentar timeout** no frontend (esperar mais que 30s)

---

## Resumo

| Ação | Tempo | Complexidade |
|------|-------|--------------|
| Apenas diagnosticar | 5 min | Baixa |
| Implementar cache | 30 min | Média |
| Dividir em janelas | 45 min | Alta |
| Aumentar timeout | 5 min | Baixa |

**Recomendação:** Cache (30 min) resolve 100% o problema

---

## Perguntas Frequentes

**P: Por que tem muitas requisições?**
R: Porque o Bling não retorna items na listagem de pedidos. Sistema precisa buscar detalhe de cada um.

**P: É bug?**
R: Não. É limitação da API Bling. Sistema está funcionando corretamente.

**P: Como outros sistemas resolvem?**
R: Cacheia order details localmente. Primeira ejecuta é lenta, próximas são rápidas.

**P: Posso aumentar o Semáforo?**
R: Não. Vai dar rate limit no Bling (máx 3 req/sec).

**P: Qual é o timeout do frontend?**
R: 30 segundos por padrão. Com 100 pedidos e cache vazio, pode atingir.

---

**Ação Mais Importante Agora:**

Rodem o script `diagnose_requests.py` e mandem o output!

Com isso, tenho exatamente o que preciso para implementar a solução certa.
