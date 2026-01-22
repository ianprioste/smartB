# 📚 Documentação - smartBling v2

Índice completo de toda a documentação do projeto.

---

## 🚀 Começar Rápido

### 1. **[QUICKSTART.md](QUICKSTART.md)** ⭐⭐⭐
   - Setup completo em 10 minutos
   - Passo-a-passo visual
   - Windows + Linux
   - Ideal para primeira vez

### 2. **[../README.md](../README.md)**
   - Visão geral do projeto
   - Arquitetura e tecnologias
   - Endpoints principais
   - Troubleshooting

---

## 📖 Documentação Técnica

### 3. **[DEVELOPMENT.md](DEVELOPMENT.md)**
   - Arquitetura detalhada
   - Decisões de design
   - Padrões utilizados (Clean Architecture, DDD)
   - Fluxos de dados

### 4. **[PROJECT_STRUCTURE.md](PROJECT_STRUCTURE.md)**
   - Estrutura completa de pastas
   - Responsabilidade de cada camada
   - Dependências entre módulos
   - Onde adicionar novos recursos

### 5. **[EXAMPLES.md](EXAMPLES.md)**
   - Exemplos práticos com cURL
   - Fluxos end-to-end
   - Casos de uso reais
   - Payloads de exemplo

---

## 🔧 Setup e Configuração

### 6. **[WINDOWS_SETUP.md](WINDOWS_SETUP.md)**
   - Guia específico para Windows
   - PowerShell scripts
   - Troubleshooting Windows
   - Alternativas ao virtualenv

### 7. **[GIT_COMMIT.md](GIT_COMMIT.md)**
   - Convenções de commit
   - Mensagens padronizadas
   - Workflow de branches

---

## 📊 Sprints e Releases

### 8. **[SPRINT1_SUMMARY.md](SPRINT1_SUMMARY.md)**
   - Sprint 1: Foundation + OAuth2
   - Jobs system
   - Token management
   - Features completas

### 9. **[SPRINT2_SUMMARY.md](SPRINT2_SUMMARY.md)**
   - Sprint 2: Governance
   - Models, Colors, Templates
   - Admin UI
   - CRUD completo

### 10. **[SPRINT3_SUMMARY.md](SPRINT3_SUMMARY.md)**
   - Sprint 3: Plan Builder
   - Dry-run preview
   - Wizard UI
   - Validações completas

### 11. **[SPRINT3_TESTING.md](SPRINT3_TESTING.md)**
   - Cenários de teste Sprint 3
   - Casos de sucesso e bloqueio
   - Dados de teste

---

## 🔧 Manutenção e Melhorias

### 12. **[../REFACTORING_RECOMMENDATIONS.md](../REFACTORING_RECOMMENDATIONS.md)** 🆕
   - Análise completa do código
   - Oportunidades de otimização
   - Plano de refatoração
   - Estimativas de esforço

---

## 📂 Arquivos do Projeto

### Backend (FastAPI)
```
backend/
├── app/
│   ├── api/           # Endpoints REST
│   ├── domain/        # Lógica de negócio
│   ├── infra/         # Infraestrutura (Bling, DB, Logs)
│   ├── models/        # ORM e Schemas
│   ├── repositories/  # Data access layer
│   └── workers/       # Celery tasks
├── alembic/           # Database migrations
└── tests/             # Testes
```

### Frontend (React)
```
frontend/
├── src/
│   ├── pages/
│   │   ├── admin/     # UI de administração
│   │   └── wizard/    # Wizard de cadastro
│   └── styles/        # CSS modules
```

### Documentação
```
doc/
├── INDEX.md           # Este arquivo
├── QUICKSTART.md      # Setup rápido
├── DEVELOPMENT.md     # Arquitetura
├── SPRINTx_SUMMARY.md # Releases
└── ...
```

---

## 🎯 Fluxo de Leitura Recomendado

### Para Desenvolvedores Novos
1. [QUICKSTART.md](QUICKSTART.md) - Setup
2. [../README.md](../README.md) - Visão geral
3. [PROJECT_STRUCTURE.md](PROJECT_STRUCTURE.md) - Estrutura
4. [DEVELOPMENT.md](DEVELOPMENT.md) - Arquitetura

### Para Contribuidores
1. [DEVELOPMENT.md](DEVELOPMENT.md) - Padrões
2. [GIT_COMMIT.md](GIT_COMMIT.md) - Commits
3. [SPRINTx_SUMMARY.md](SPRINT3_SUMMARY.md) - Estado atual
4. [../REFACTORING_RECOMMENDATIONS.md](../REFACTORING_RECOMMENDATIONS.md) - Melhorias

### Para Testes e QA
1. [EXAMPLES.md](EXAMPLES.md) - Casos de uso
2. [SPRINT3_TESTING.md](SPRINT3_TESTING.md) - Cenários de teste
3. [QUICKSTART.md](QUICKSTART.md) - Como rodar

---

## 📝 Notas

### Documentação Consolidada (22/01/2026)
- ✅ Removido duplicação (QUICKSTART_v2, doc/README)
- ✅ Criado REFACTORING_RECOMMENDATIONS.md
- ✅ Atualizado INDEX.md

### Próximas Sprints
- 📌 Sprint 4: Execução real (criar produtos no Bling)
- 📌 Sprint 5: Composições e estruturas complexas
- 📌 Sprint 6: FIX mode (correção de produtos legados)

---

**Última atualização:** 22/01/2026  
**Versão:** 0.3.0 (Sprint 3 completo)

---

## ⚙️ Específico do Sistema

### 8. **[WINDOWS_SETUP.md](WINDOWS_SETUP.md)**
   - Problemas Windows-específicos
   - Celery solo pool
   - Solução de erros

---

## 🗺️ Mapa Visual

```
COMEÇAR AQUI
    ↓
[QUICKSTART.md] ← 5 min
    ↓
Quer entender tudo?
    ↓
[README.md] ← Overview
    ↓
Quer ver exemplos?
    ↓
[EXAMPLES.md] ← Práticos
    ↓
Quer estudar arquitetura?
    ↓
[DEVELOPMENT.md] ← Design
[PROJECT_STRUCTURE.md] ← Estructura
    ↓
Quer histórico do Sprint?
    ↓
[SPRINT1_SUMMARY.md] ← Entrega
[CODE_REVIEW.md] ← Análise
    ↓
Problema no Windows?
    ↓
[WINDOWS_SETUP.md] ← Solução
```

---

## 📋 Checklist de Leitura

- [ ] **Novo desenvolvedor**: QUICKSTART → README → EXAMPLES
- [ ] **Arquiteto**: DEVELOPMENT → PROJECT_STRUCTURE → CODE_REVIEW
- [ ] **DevOps**: WINDOWS_SETUP → README (Troubleshooting)
- [ ] **Reviewer**: SPRINT1_SUMMARY → CODE_REVIEW → DEVELOPMENT
- [ ] **Usuário Final**: QUICKSTART → EXAMPLES

---

## 🔗 Links Rápidos

| Documento | Para | Tempo |
|-----------|------|-------|
| QUICKSTART | Rodar rápido | 5 min |
| README | Overview | 10 min |
| EXAMPLES | Ver na prática | 15 min |
| DEVELOPMENT | Estudar design | 30 min |
| PROJECT_STRUCTURE | Entender código | 20 min |
| SPRINT1_SUMMARY | Histórico | 10 min |
| CODE_REVIEW | Melhorias | 15 min |
| WINDOWS_SETUP | Troubleshoot | 10 min |

**Total: ~2h para estudo completo**

---

## 🆘 Problemas Comuns

| Problema | Veja |
|----------|------|
| Não consigo rodar | QUICKSTART (seção Troubleshooting) |
| OAuth não funciona | README (seção Bling Setup) |
| Worker não inicia | WINDOWS_SETUP |
| Não entendo arquitetura | DEVELOPMENT + PROJECT_STRUCTURE |
| Quero exemplos | EXAMPLES |
| Quer saber o que foi feito | SPRINT1_SUMMARY |

---

## 🎓 Aprendizado

### Iniciante
1. QUICKSTART (get it running)
2. EXAMPLES (see it work)
3. README (understand overview)

### Intermediário
1. DEVELOPMENT (how it's designed)
2. PROJECT_STRUCTURE (where's what)
3. CODE_REVIEW (best practices)

### Avançado
1. CODE_REVIEW (patterns)
2. DEVELOPMENT (deep dive)
3. Código-fonte em `/backend/app/`

---

## 📝 Notas

- Todos os exemplos funcionam com `.venv` ativado
- Scripts estão em `/scripts/` (Windows + Linux/Mac)
- Banco de dados não precisa de setup manual (Alembic automático)
- OAuth2 requer registro prévio no Bling

---

**Última atualização:** 21 Jan 2026  
**Versão:** Sprint 1  
**Status:** ✅ Production Ready
