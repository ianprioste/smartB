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
**Component:** `PlanPrtexto limpo sem emojis)
- ✅ Dependências visíveis
- ✅ Templates identificados em português
- ✅ Motivos de bloqueio claros
- ✅ Modal de loading com status progressivo

**Modal de Loading:**
- ✅ Overlay em tela cheia
- ✅ Spinner animado
- ✅ Mensagens progressivas:
  - "📋 Validando dados..."
  - "🔍 Buscando templates configurados..."
  - "🎨 Calculando SKUs e variações..."
  - "⚙️ Geranrincipal Estampado | Criar | - | CAM/Principal Estampado | - |
| CAMSTPVBRP | Variação Estampada | Bloqueado | CAMBRP, CAMSTPV | CAM/Principal Estampado
  - "✅ Plano gerado com sucesso!"
- ✅ Auto-dismiss ao completarco
- ✅ Tabela completa de SKUs
- ✅ Status coloridos (🟢🟡🔵🔴)
- ✅ Dependências visíveis
- ✅ Templates identificados
- ✅ Motivos de bloqueio claros

**Se houver BLOCKED:**
- ⚠️ Alerta destacado
- 🚫 Botão "Executar" desabilitado
- 💬 Mensagem: "Corrija Templates antes de continuar"

**Tabela de Preview:** (sem emojis)
- ✅ Animações suaves
- ✅ Modal de loading com spinner e transições

### 9. Melhorias de UX ✅
- ✅ Template labels em português em todos os lugares
- ✅ Info box colapsável (minimizado por padrão)
- ✅ Template upsert (substituição sem conflito)
- ✅ Busca de produtos inclui variações
- ✅ Token auto-refresh com modal de reauth
- ✅ Sem modo manual (automático apenas)| Dependências | Template | Motivo |
|-----|------|------|-------------|----------|--------|
| CAMSTPV | PARENT_PRINTED | 🟢 CREATE | STMCAMSTPV | CAM/PARENT_PRINTED | - |
| CAMSTPVBRP | VARIATION_PRINTED | 🔴 BLOCKED | CAMBRP, STMCAMSTPV | CAM/PARENT_PRINTED | MISSING_TEMPLATE |

### 8. Estilos ✅
**Arquivo:** `frontend/src/styles/wizard.css`

Design moderno e responsivo:
- ✅ Barra de progresso visual
- ✅ Cards interativos
- ✅ Tabela responsiva
- ✅ Status com cores semânticas
- ✅ Animações suaves

### 9. Navegação ✅
- Botão "🪄 Novo Cadastro" na barra de navegação admin
- Estilo destacado (verde, animado)
- Acessível de qualquer página admin

---

## 🧪 Como Testar

### 1. Aplicar Migration
```bash
cd backend
python init_alembic.py upgrade head
```

### 2. Iniciar Backend
```bash
cd backend
python run.py
```

### 3. Iniciar Frontend
```bash
cd frontend
npm run dev
```

### 4. Acessar Wizard
1. Navegar para: http://localhost:5173/wizard/new
2. Preencher dados da estampa
3. Selecionar modelos e tamanhos
4. Selecionar cores
5. Gerar previewPARENT_PRINTED
  - BL: BASE_PLAIN
### 5. Cenários de Teste

#### ✅ Sucesso (sem bloqueios)
**Pré-requisitos:**
- Modelos CAM e BL configurados
- Cores BR e OW configuradas
- Templates configurados:
  - CAM: BASE_PLAIN, STAMPPARENT_PRINTED

**Resultado esperado:**
- Items do CAM com status BLOCKED
- Mensagem: "Model CAM does not have template PARENT_PRINTED
- Botão "Executar" habilitado (mas não funcional nesta sprint)

#### 🔴 Bloqueio (template faltando)
**Cenário:**
- Modelo CAM sem template STAMP

**Resultado esperado:**
- Items do CAM com status BLOCKED
- Mensagem: "Model CAM does not have template STAMP configured"
- Botão "Executar" desabilitado
- Alerta: "Existem bloqueios. Corrija Templates antes de continuar."

---

## 🚫 FORA DO ESCOPO (Não Implementado)

❌ Criar produto no Bling
❌ Atualizar produto no Bling
❌ Criar composição
❌ cloneInfo
❌ Worker real de execução
❌ Tela de listagem de planos salvos

---

## ✅ Critérios de Aceite (DoD)

✅ Consigo gerar preview sem alterar o Bling
✅ Templates faltantes bloqueiam o plano
✅ SKUs são gerados corretamente seguindo as regras
✅ Tamanhos por modelo funcionam independentemente
✅ Preview mostra Criar / Atualizar / OK / Bloqueado em português
✅ Wizard é compreensível sem documentação externa
✅ Design responsivo e moderno
✅ Modal de loading informa progresso ao usuário
✅ Labels em português em todos os lugares
✅ Template upsert funciona sem conflito
✅ Busca de produtos inclui variações
✅ Token auto-refresh funciona corretamente

---

## 🔜 Próximas Sprints (Não Fazer Agora)

**Sprint 4: Execução Real**
- Executar plano a partir do Plan
- Criar produtos no Bling
- Jobs assíncronos

**Sprint 5: Composição**
- Criar composições
- cloneInfo=false
- Estruturas pai/filho

**Sprint 6: FIX**
- Correção de produtos legados
- Comparação com padrão
- Atualização em massa

---

## 📁 Arquivos Criados/Modificados

### Backend
- ✅ `app/domain/sku_engine.py` (NOVO)
- ✅ `app/domain/plan_builder_new.py` (NOVO)
- ✅ `app/models/enums.py` (MODIFICADO)
- ✅ `app/models/database.py` (MODIFICADO)
- ✅ `app/infra/bling_client.py` (MODIFICADO - add BlingRefreshTokenExpiredError, remove tipo filter)
- ✅ `app/api/auth.py` (MODIFICADO - add GET /auth/bling/connect)
- ✅ `app/api/config_templates.py` (MODIFICADO - upsert pattern)
- ✅ `app/repositories/model_template_repo.py` (MODIFICADO - add create_or_update)
- ✅ `app/models/schemas.py` (MODI - with loading modal)
- ✅ `src/App.jsx` (MODIFICADO)
- ✅ `src/pages/admin/AdminPages.jsx` (MODIFICADO - reauth modal, collapsible info, Portuguese labels
- ✅ `app/main.py` (MODIFICADO)
- ✅ `app/infra/bling_client.py` (MODIFICADO - add get_produtos)
- ✅ `alembic/versions/003_sprint3_plans.py` (NOVO)

### Frontend
- ✅ `src/pages/wizard/WizardNew.jsx` (NOVO)
- ✅ `src/styles/wizard.css` (NOVO) e polida** com feedback do usuário!

O sistema agora pode:
- ✅ Gerar planos inteligentes
- ✅ Validar configurações antes de executar
- ✅ Mostrar preview completo e compreensível em português
- ✅ Bloquear execução quando há problemas
- ✅ Proporcionar experiência visual e intuitiva
- ✅ Gerenciar tokens automaticamente
- ✅ Buscar produtos incluindo variações
- ✅ Substituir templates sem conflitos
- ✅ Informar progresso durante geração

A Sprint 3 está **100% implementada** e pronta para uso!

O sistema agora pode:
- ✅ Gerar planos inteligentes
- ✅ Validar configurações antes de executar
- ✅ Mostrar preview completo e compreensível
- ✅ Bloquear execução quando há problemas
- ✅ Proporcionar experiência visual e intuitiva

**Esta sprint transforma configuração em decisão.**
**Nenhuma execução real acontece ainda - isso é Sprint 4!**
