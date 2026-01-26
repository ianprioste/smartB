# Sprint 3 - Plan Builder + Dry-Run + Preview

## ✅ Implementação Completa + Melhorias

Esta sprint implementa o motor de planejamento (Plan Builder) que gera planos completos de criação/correção de produtos **SEM ESCREVER NO BLING**.

**Melhorias após feedback:**
- ✅ STAMP removido (apenas BASE_PLAIN, PARENT_PRINTED, VARIATION_PRINTED)
- ✅ Labels em português user-friendly em todos os lugares
- ✅ Modal de loading com status progressivo
- ✅ Ações sem emoji (texto limpo com cores)
- ✅ Template upsert (substituição ao invés de conflito)
- ✅ Busca de produtos inclui variações
- ✅ Info box colapsável (minimizado por padrão)
- ✅ Token auto-refresh com fail-fast
- ✅ Modal de reauth ao invés de modo manual

## 🎯 Objetivo Alcançado

✅ Geração de planos completos com preview
✅ Validação de regras de negócio, SKUs e templates
✅ Status por SKU: CREATE, UPDATE, NOOP, BLOCKED
✅ Interface wizard intuitiva e visual
✅ Bloqueio de execução quando há problemas
✅ Experiência de usuário polida e em português

---

## 📦 Backend - Implementado

### 1. SkuEngine (Núcleo Lógico) ✅
**Arquivo:** `backend/app/domain/sku_engine.py`

Motor determinístico de geração de SKUs:
- `parent_printed()` - Produto pai: `{MODEL_CODE}{PRINT_CODE}`
- `variation_printed()` - Variação: `{MODEL_CODE}{PRINT_CODE}{COLOR_CODE}{SIZE}`
- `base_plain()` - Base lisa: `{MODEL_CODE}{COLOR_CODE}{SIZE}`

**Nota:** STAMP foi removido conforme solicitação do usuário.

**Características:**
- ✅ Isolado e testável
- ✅ Sem dependências externas
- ✅ Funções puras (sem side effects)
- ✅ Validações de componentes

### 2. Plan Builder NEW ✅
**Arquivo:** `backend/app/domain/plan_builder_new.py`

Motor de planejamento para novos cadastros:

**Validações Obrigatórias:**
- ✅ Templates obrigatórios por modelo (BASE_PLAIN, PARENT_PRINTED)
- ✅ Integridade de tamanhos (todos devem existir em allowed_sizes)
- ✅ Modelos e cores devem estar configurados
- ✅ Cada modelo usa seus próprios tamanhos

**Geração do Plano:**
```json
{
  "planVersion": "1.0",
  "type": "NEW_PRINT",
  "summary": {
    "models": 2,
    "colors": 2,
    "total_skus": 18,
    "create_count": 10,
    "update_count": 0,
    "noop_count": 3,
    "blocked_count": 5
  },
  "items": [...]
}
```

**Status de Items:**
- 🟢 **Criar** - SKU não existe no Bling
- 🟡 **Atualizar** - SKU existe mas precisa atualização
- 🔵 **OK** - SKU existe e está correto
- 🔴 **Bloqueado** - Dependência ou template faltando

**Labels de Template (em português):**
- **Base Lisa** - Produto base sem estampa
- **Principal Estampado** - Produto pai com estampa
- **Variação Estampada** - Variação específica (cor/tamanho)

### 3. Persistência ✅
**Migration:** `backend/alembic/versions/003_sprint3_plans.py`
**Model:** `backend/app/models/database.py` - `PlanModel`
**Repository:** `backend/app/repositories/plan_repo.py`

Tabela `plans`:
- `id` - UUID
- `tenant_id` - UUID
- `type` - Enum (NEW_PRINT, FIX)
- `status` - Enum (DRAFT, EXECUTED)
- `input_payload` - JSON (request original)
- `plan_payload` - JSON (plano gerado)
- `created_at`, `executed_at` - Timestamps

### 4. API Endpoints ✅
**Arquivo:** `backend/app/api/plans.py`

#### `POST /plans/new` - Criar Plano (Dry-run)
**Características:**
- ✅ Não cria job
- ✅ Não escreve no Bling
- ✅ Consulta Bling apenas para leitura (verifica existência)
- ✅ Retorna preview completo

**Request:**
```json
{
  "print": {
    "code": "STPV",
    "name": "Santa Teresinha Pequena Via"
  },
  "models": [
    { "code": "CAM", "sizes": ["P", "M", "G"] },
    { "code": "BL" }
  ],
  "colors": ["BR", "OW"]
}
```

**Response:** Plan completo com items e summary

#### `POST /plans/new/save` - Salvar Plano (Opcional)
- Persiste plano no banco
- Status = DRAFT
- Permite revisão posterior

### 5. Enums Adicionados ✅
**Arquivo:** `backend/app/models/enums.py`

```python
class PlanTypeEnum(str, enum.Enum):
    NEW_PRINT = "NEW_PRINT"
    FIX = "FIX"

class PlanStatusEnum(str, enum.Enum):
    DRAFT = "DRAFT"
    EXECUTED = "EXECUTED"

class PlanItemActionEnum(str, enum.Enum):
    CREATE = "CREATE"
    UPDATE = "UPDATE"
    NOOP = "NOOP"
    BLOCKED = "BLOCKED"
```

---

## 🎨 Frontend - Implementado

### 6. Wizard de Novo Cadastro ✅
**Arquivo:** `frontend/src/pages/wizard/WizardNew.jsx`
**Rota:** `/wizard/new`

**Fluxo em 4 Passos:**

#### **Passo 1: Dados da Estampa**
- Código da estampa (ex: STPV)
- Nome da estampa (ex: Santa Teresinha Pequena Via)

#### **Passo 2: Modelos e Tamanhos**
- Multi-select de modelos
- Para cada modelo selecionado:
  - Mostra tamanhos disponíveis (allowed_sizes)
  - Permite desmarcar tamanhos (subconjunto)
  - Valida que pelo menos um tamanho esteja selecionado

#### **Passo 3: Cores**
- Multi-select de cores
- Validação: pelo menos uma cor

#### **Passo 4: Preview**
- Chama `POST /plans/new`
- Exibe plano completo

### 7. Tela de Preview ✅
**Component:** `PlanPreview.jsx`
- ✅ Cards de resumo
- ✅ Tabela completa de SKUs
- ✅ Status coloridos
- ✅ Dependências visíveis
- ✅ Templates identificados
- ✅ Motivos de bloqueio claros
- ✅ Modal de loading com mensagens progressivas

### 8. UX Ajustada ✅
- ✅ Texto limpo sem emojis em ações
- ✅ Auto-refresh de token (fail-fast)
- ✅ Modal de reauth
- ✅ Info box colapsável
- ✅ Busca Bling inclui variações

---

## 🔎 Observações Importantes

1. **Nenhuma escrita no Bling** nesta sprint — apenas leitura/preview.
2. **BLOCKED**: itens ficam bloqueados se faltar template/dependência.
3. **Templates exigidos**: BASE_PLAIN e PARENT_PRINTED para cada modelo.
4. **STAMP** removido do fluxo.

---

## ✅ Resultado

- Planejamento completo sem efeitos colaterais.
- Usuário entende exatamente o que seria criado/atualizado.
- Sistema pronto para Sprint 4 (execução real).

---

## 🚀 Próximos Passos (Sprint 4)

- POST /plans/{id}/execute
- Worker para criar SKUs no Bling (CREATE/UPDATE)
- Respeitar BLOCKED/NOOP (não executar)
- Auditoria e logs detalhados por SKU
- Alertas de erro na execução

---

## 🧪 Teste Rápido (Manual)

```bash
POST http://localhost:8000/plans/new
Content-Type: application/json

{
  "print": {"code": "STPV", "name": "Santa Teresinha Pequena Via"},
  "models": [{"code": "CAM", "sizes": ["P", "M", "G"]}],
  "colors": ["BR", "OW"]
}
```

Resposta: plano completo com status por SKU.

---

## 📌 O Que Foi Ajustado

- Labels traduzidos para PT-BR
- Preview seguro (sem crash mesmo faltando template)
- Bloqueio de execução quando depende de template ausente
- Modal de loading com status
- Remoção de STAMP

---

## ✅ Conclusão

Sprint 3 entrega o planejamento completo com preview e bloqueios de execução quando necessário. O backend valida regras de negócio e o frontend oferece uma experiência guiada e clara. Pronto para acionar execução real no Sprint 4.
