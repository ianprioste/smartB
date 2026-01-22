# 🧪 Guia de Teste - Sprint 3

## ✅ Servidores Iniciados

- ✅ Backend: http://localhost:8000
- ✅ Frontend: http://localhost:5173
- ✅ Migration aplicada (tabela `plans` criada)

## 📋 Pré-requisitos para Teste

### 1. Configurar Modelos
Acesse: http://localhost:5173/admin/models

Criar pelo menos 2 modelos, exemplo:
- **CAM** - Camiseta
  - Tamanhos: P, M, G, GG
- **BL** - Babylook
  - Tamanhos: P, M, G

### 2. Configurar Cores
Acesse: http://localhost:5173/admin/colors

Criar pelo menos 2 cores, exemplo:
- **BR** - Branca
- **OW** - Off-White

### 3. Configurar Templates
Acesse: http://localhost:5173/admin/templates

Para cada modelo (CAM e BL), configurar:
- ✅ **BASE_PLAIN** - Produto liso base
- ✅ **STAMP** - Produto estampa
- ✅ **PARENT_PRINTED** - Produto pai estampado

**⚠️ IMPORTANTE:** Use produtos reais do Bling que existam!

## 🪄 Testando o Wizard

### Acesso
Clique no botão verde "🪄 Novo Cadastro" no menu superior
OU
Acesse diretamente: http://localhost:5173/wizard/new

### Passo 1: Dados da Estampa
1. **Código:** STPV (ou qualquer código único)
2. **Nome:** Santa Teresinha Pequena Via
3. Clicar em "Próximo"

### Passo 2: Modelos e Tamanhos
1. Selecionar checkbox dos modelos (CAM, BL)
2. Para cada modelo selecionado:
   - Os tamanhos disponíveis aparecerão
   - Você pode desmarcar tamanhos se quiser
   - Ao menos 1 tamanho deve ficar selecionado
3. Clicar em "Próximo"

### Passo 3: Cores
1. Selecionar cores desejadas (BR, OW)
2. Clicar em "🔍 Gerar Preview"

### Passo 4: Preview
**O sistema irá:**
1. Gerar todos os SKUs possíveis
2. Consultar o Bling (apenas leitura)
3. Determinar status de cada SKU

**Você verá:**
- 📊 Cards resumo com estatísticas
- 📋 Tabela completa de SKUs
- 🎨 Status coloridos por linha

## 🎨 Status Possíveis

### 🟢 CREATE (Verde)
- SKU não existe no Bling
- Será criado na próxima sprint
- Normal em primeiro uso

### 🟡 UPDATE (Amarelo)
- SKU existe mas precisa atualização
- Diferenças detectadas no nome/formato
- **Nota:** Atualmente sempre retorna CREATE na primeira vez

### 🔵 NOOP (Azul)
- SKU já existe e está correto
- Nenhuma ação necessária
- Aparece em re-execuções

### 🔴 BLOCKED (Vermelho)
- **Template faltando**
- **Dependência não encontrada**
- Execução bloqueada até correção

## ⚠️ Cenários de Bloqueio

### Teste 1: Template Faltando
1. Remover o template STAMP do modelo CAM
2. Tentar gerar plano com CAM
3. **Resultado esperado:**
   - SKUs do CAM com status BLOCKED
   - Mensagem: "Model CAM does not have template STAMP configured"
   - Botão "Executar" desabilitado
   - Alerta vermelho no topo

### Teste 2: Sucesso Completo
1. Garantir todos os templates configurados
2. Gerar plano normalmente
3. **Resultado esperado:**
   - Todos os SKUs com status CREATE
   - Botão "Executar" habilitado (mas não funcional ainda)
   - Nenhum bloqueio

## 📊 Exemplo de SKUs Gerados

Para **STPV** com modelo **CAM** (P,M,G) e cores **BR,OW**:

### Estampas (STM)
- `STMCAMSTPV` - Estampa do CAM

### Pais Estampados
- `CAMSTPV` - Pai estampado CAM

### Bases Lisas
- `CAMBRP`, `CAMBRM`, `CAMBRG` - Bases brancas
- `CAMOWP`, `CAMOWM`, `CAMOWG` - Bases off-white

### Variações Estampadas
- `CAMSTPVBRP`, `CAMSTPVBRM`, `CAMSTPVBRG` - Variações brancas
- `CAMSTPVOWP`, `CAMSTPVOWM`, `CAMSTPVOWG` - Variações off-white

**Total esperado:** 13 SKUs por modelo

## 🚫 O Que NÃO Acontece (Correto!)

❌ Não cria produtos no Bling
❌ Não altera produtos existentes
❌ Não cria composições
❌ Não inicia jobs
❌ Não executa nada de fato

✅ Apenas mostra o que **SERIA** feito
✅ Esta é a proposta da Sprint 3!

## 🐛 Troubleshooting

### Erro: "Failed to fetch configuration"
- Verificar se backend está rodando (http://localhost:8000)
- Verificar se há modelos/cores cadastrados

### Erro: "Model XXX not found"
- Código do modelo não está cadastrado
- Verificar em /admin/models

### Erro: "Color XXX not found"
- Código da cor não está cadastrado
- Verificar em /admin/colors

### Preview não carrega
- Abrir DevTools (F12)
- Verificar console para erros
- Verificar Network tab para status das requisições

## 📝 Teste Manual da API

### Usando curl/Postman

```bash
POST http://localhost:8000/plans/new
Content-Type: application/json

{
  "print": {
    "code": "STPV",
    "name": "Santa Teresinha Pequena Via"
  },
  "models": [
    {"code": "CAM", "sizes": ["P", "M", "G"]},
    {"code": "BL"}
  ],
  "colors": ["BR", "OW"]
}
```

**Resposta esperada:**
```json
{
  "planVersion": "1.0",
  "type": "NEW_PRINT",
  "summary": {
    "models": 2,
    "colors": 2,
    "total_skus": 26,
    "create_count": 26,
    "update_count": 0,
    "noop_count": 0,
    "blocked_count": 0
  },
  "items": [...],
  "has_blockers": false
}
```

## ✅ Critérios de Sucesso

A Sprint 3 está funcionando se:

1. ✅ Consigo acessar o wizard
2. ✅ Consigo preencher os 3 passos
3. ✅ Preview é gerado sem erros
4. ✅ SKUs aparecem corretamente formatados
5. ✅ Status coloridos aparecem
6. ✅ Bloqueios funcionam quando template falta
7. ✅ Nenhum produto é criado no Bling
8. ✅ Interface é clara e compreensível

## 🔜 Próxima Sprint (Sprint 4)

A Sprint 4 implementará:
- Execução real do plano
- Criação de produtos no Bling
- Jobs assíncronos
- Tracking de progresso

**POR ENQUANTO:** O botão "Executar" não faz nada - isso é esperado!

## 📞 Feedback

Se encontrar problemas:
1. Verificar console do navegador (F12)
2. Verificar logs do backend
3. Conferir configurações de modelos/cores/templates
4. Verificar se Bling está acessível (se houver auth)

---

**Bom teste! 🚀**
