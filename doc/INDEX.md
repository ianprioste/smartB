# 📚 Documentação - smartBling v2

Índice completo de toda a documentação do projeto.

---

## 🚀 Começar

### 1. **[QUICKSTART.md](QUICKSTART.md)** ⭐⭐⭐
   - Setup em 5 minutos
   - Passo-a-passo visual
   - Ideal para primeira vez

### 2. **[README.md](README.md)**
   - Visão geral completa
   - Endpoints e configuração
   - Troubleshooting

---

## 📖 Documentação Técnica

### 3. **[DEVELOPMENT.md](DEVELOPMENT.md)**
   - Arquitetura detalhada
   - Decisões de design
   - Pattern utilizado (clean architecture)

### 4. **[PROJECT_STRUCTURE.md](PROJECT_STRUCTURE.md)**
   - Estrutura de pastas
   - O que cada camada faz
   - Dependências entre módulos

### 5. **[EXAMPLES.md](EXAMPLES.md)**
   - Exemplos práticos com cURL
   - Fluxos end-to-end
   - Casos de uso reais

---

## 📊 Projeto

### 6. **[SPRINT1_SUMMARY.md](SPRINT1_SUMMARY.md)**
   - O que foi entregue
   - Checklist de features
   - Base para Sprint 2

### 7. **[CODE_REVIEW.md](../CODE_REVIEW.md)**
   - Análise de código
   - Melhorias futuras
   - Padrões sugeridos

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
