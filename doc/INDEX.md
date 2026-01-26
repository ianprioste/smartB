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
   - Principais links técnicos
   - Troubleshooting rápido

---

## 📖 Documentação Técnica

### 3. **[ARCHITECTURE.md](ARCHITECTURE.md)**
   - Visão completa e diagramas
   - Padrões (Repo, Multi-tenant, Services)
   - Segurança, performance e escalabilidade

### 4. **[PROJECT_STRUCTURE.md](PROJECT_STRUCTURE.md)**
   - Estrutura de pastas
   - Responsabilidade de cada camada
   - Onde adicionar novos recursos

### 5. **[API.md](API.md)**
   - Endpoints, exemplos e erros
   - Autenticação e rate limiting

### 6. **[TESTING.md](TESTING.md)**
   - Estratégia de testes
   - Estrutura de pastas e fixtures
   - Como rodar com cobertura

### 7. **[DEPLOYMENT.md](DEPLOYMENT.md)**
   - Dev/Staging/Prod
   - Checklists de segurança e saúde

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

## 📊 Sprints e Status (arquivados)

- Ver arquivos legados em `doc/archive/` (ex: SPRINT3_SUMMARY.md, SPRINT3_TESTING.md)

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
├── ARCHITECTURE.md    # Arquitetura
├── API.md             # Endpoints
├── TESTING.md         # Testes
├── DEPLOYMENT.md      # Deploy
├── PROJECT_STRUCTURE.md # Estrutura
├── WINDOWS_SETUP.md   # Windows
└── archive/           # Materiais legados
```

---

## 🎯 Fluxo de Leitura Recomendado

### Para Desenvolvedores Novos
1. [QUICKSTART.md](QUICKSTART.md) - Setup
2. [../README.md](../README.md) - Visão geral
3. [PROJECT_STRUCTURE.md](PROJECT_STRUCTURE.md) - Estrutura
4. [ARCHITECTURE.md](ARCHITECTURE.md) - Arquitetura

### Para Contribuidores
1. [ARCHITECTURE.md](ARCHITECTURE.md) - Padrões
2. [PROJECT_STRUCTURE.md](PROJECT_STRUCTURE.md) - Estrutura de código
3. Histórico: ver `doc/archive/` (ex: SPRINT3_SUMMARY.md)

### Para Testes e QA
1. [API.md](API.md) - Casos de uso e payloads
2. [QUICKSTART.md](QUICKSTART.md) - Como rodar

---

## 📝 Notas

### Documentação Consolidada (22/01/2026)
- ✅ Removido duplicação (QUICKSTART_v2, doc/README)
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
[API.md] ← Exemplos e payloads
   ↓
Quer estudar arquitetura?
   ↓
[ARCHITECTURE.md] ← Design
[PROJECT_STRUCTURE.md] ← Estrutura
   ↓
Quer histórico do Sprint?
   ↓
Arquivos legados em `doc/archive/`
   ↓
Problema no Windows?
    ↓
[WINDOWS_SETUP.md] ← Solução
```

---

## 📋 Checklist de Leitura

- [ ] **Novo desenvolvedor**: QUICKSTART → README → API
- [ ] **Arquiteto**: ARCHITECTURE → PROJECT_STRUCTURE → API
- [ ] **DevOps**: WINDOWS_SETUP → README (Troubleshooting)
- [ ] **Reviewer**: ARCHITECTURE
- [ ] **Usuário Final**: QUICKSTART → API

---

## 🔗 Links Rápidos

| Documento | Para | Tempo |
|-----------|------|-------|
| QUICKSTART | Rodar rápido | 5 min |
| README | Overview | 10 min |
| API | Ver payloads/exemplos | 15 min |
| ARCHITECTURE | Estudar design | 30 min |
| PROJECT_STRUCTURE | Entender código | 20 min |
| WINDOWS_SETUP | Troubleshoot | 10 min |

**Total: ~2h para estudo completo**

---

## 🆘 Problemas Comuns

| Problema | Veja |
|----------|------|
| Não consigo rodar | QUICKSTART (seção Troubleshooting) |
| OAuth não funciona | README (seção Bling Setup) |
| Worker não inicia | WINDOWS_SETUP |
| Não entendo arquitetura | ARCHITECTURE + PROJECT_STRUCTURE |
| Quero exemplos/payloads | API |
| Quer saber o que foi feito | ARCHITECTURE |

---

## 🎓 Aprendizado

### Iniciante
1. QUICKSTART (get it running)
2. API (see it work)
3. README (understand overview)

### Intermediário
1. ARCHITECTURE (how it's designed)
2. PROJECT_STRUCTURE (where's what)
3. API (payloads)

### Avançado
1. ARCHITECTURE (patterns)
2. Código-fonte em `/backend/app/`
3. API/TESTING para contratos e cobertura

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
