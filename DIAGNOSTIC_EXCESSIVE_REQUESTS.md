# 🔍 Diagnóstico: Muitas Requisições Bling

## Problema Relatado

> "Está fazendo muitas requests no bling ainda quando tento filtrar um Evento"

---

## Causa Raiz Provável

O problema é que **o `/pedidos/vendas` do Bling NÃO retorna o campo `itens`** na resposta da listagem.

### O Que Significa?

Quando fazemos:
```
GET /pedidos/vendas?dataInicial=...&dataFinal=...
```

O Bling retorna algo como:
```json
{
  "data": [
    {
      "id": 1001,
      "numero": "PED-001",
      "data": "2024-03-01",
      "total": 1000.00,
      "itens": []  // ← VAZIO na maioria dos Blings
    }
  ]
}
```

### Consequência

O código vê que `itens` está vazio e faz:
```
Fase 1: Busca pedidos (1 call)
Fase 2: Para CADA pedido vazio, busca detalhe (N calls)

Total = 1 + N calls (vs ideal de 1 call)
```

---

## Como Diagnosticar

### 1. Verificar Logs do Backend

Ao filtrar um evento, procure por logs como:

```
event_sales_phase1_done orders_in_period=42 phase1_matched=5 phase1_skipped=0 phase2_needed=37
event_sales_phase2_start making_api_calls=37
event_sales_filter_done ... phase2_api_calls=37 total_api_calls=38
```

**Se `phase2_needed` é alto (>80% dos pedidos):**
→ Confirma que Bling não retorna items na lista

**Se `phase2_needed` é zero:**
→ Sistema está otimizado corretamente

### 2. Verificar Resposta do Bling Manualmente

```bash
curl -H "Authorization: Bearer TOKEN" \
  "https://www.bling.com.br/Api/v3/pedidos/vendas?dataInicial=2024-03-01&dataFinal=2024-03-31&limite=1"
```

Procure pelo campo `itens`:
- ✅ Se tem dados: Sistema está funcionando
- ❌ Se está vazio: Bling não inclui items na lista

### 3. Usar Script de Diagnóstico

```bash
cd backend
python trace_api_calls.py
```

Mostra:
```
📡 API CALL ANALYSIS

Total calls: 38
  order-list-fetch: 1 calls (0.45s)
  order-detail-fetch: 37 calls (28.50s)

⚠️  WARNING: 37 order detail fetches is TOO MANY
```

---

##Soluções Possíveis

### Solução 1: Verificar com Suporte Bling (Recomendado)

Entre em contato com Bling e pergunte:
> "Sua API `/pedidos/vendas` retorna o campo `itens` (items do pedido) quando fazemos listagem com `dataInicial` e `dataFinal`?"

Se NÃO, pergunte se há:
1. Parâmetro especial para incluir items
2. Endpoint alternativo que inclui items
3. Versão diferente da API

### Solução 2: Implementar Cache Local

Se Bling não retorna items na lista, podemos:

1. **Cache de Detalhes:**
   - Primeira vez: Busca detalhe para cada pedido (lento)
   - Reexecuta: Usa cache local (instant)

2. **Implementação:**
```python
# Pseudocódigo
orders = fetch_orders(start, end)  # 1 call

# Usa cache se disponível, senão busca
for order in orders:
    detail = get_cached_or_fetch(order.id)  # N calls na primeira vez
    items = extract_items(detail)
```

### Solução 3: Reduzir Parallelização Inteligente

Se mesmo assim há muitos calls:

1. **Aumentar Semáforo:**
   - Atual: `Semaphore(8)` = 8 paralelos
   - Novo: `Semaphore(3)` = respeita rate limit Bling (3 req/sec)
   - Resultado: Mais lento, mas sem timeout

2. **Implementação:**
```python
# Em events.py, linha ~470
semaphore = asyncio.Semaphore(3)  # Reduzir de 8
```

### Solução 4: Windowing (Dividir Período)

Se período é muito grande (ex: 6 meses), dividir em janelas menores:

```python
# Buscar em pedaços: 1 semana por vez
# Reduz número de pedidos por busca
```

---

## Checklist de Diagnóstico

Execute na ordem:

- [ ] Verificar logs ao filtrar evento
- [ ] Procurar por `phase2_needed` nos logs
- [ ] Se > 80% dos pedidos precisam detalhe: **é o problema**
- [ ] Testar endpoint de Bling manualmente
- [ ] Contactar Bling se não retorna items
- [ ] Implementar cache se necessário

---

## Próximos Passos

### Para Você (Agora)

1. Execute:
   ```bash
   cd backend
   python run.py
   ```

2. Va para frontend e filtre um evento

3. Procure nos logs:
   ```
   event_sales_phase1_done ... phase2_needed=X
   ```

4. Reporte o valor de `phase2_needed` e `orders_in_period`

### Para Nós (Com Dados)

Com essas informações, eu posso:
1. Confirmar se é o problema da API Bling
2. Implementar solução específica (cache, windowing, etc)
3. Testes para validar nova solução

---

## Exemplo de Saída

### Cenário Péssimo (Sem Items na Lista)
```
orders_in_period=100
phase1_matched=0     ← Nenhum matched
phase2_needed=100    ← Precisa detalhe para TODOS
total_api_calls=101  (1 lista + 100 detalhes)
```

### Cenário Ideal
```
orders_in_period=100
phase1_matched=45    ← Todos matched na lista
phase2_needed=0      ← Nenhum precisa detalhe
total_api_calls=1    (apenas lista)
```

### Cenário Aceitável
```
orders_in_period=100
phase1_matched=40    ← Maioria matched
phase2_needed=60     ← Apenas alguns precisam detalhe
total_api_calls=61   (1 lista + 60 detalhes)
```

---

## Resumo

| Situação | Chamadas | Status | Solução |
|----------|----------|--------|---------|
| Items na lista | N+1 | ✅ Bom | Nenhuma |
| Items não na lista | 2N+1 | ❌ Ruim | Cache ou windowing |
| Bling rate limit | Timeout | ❌ Crítico | Reduzir paralelo |

**Aguardo seu diagnóstico para implementar a solução correta!**
