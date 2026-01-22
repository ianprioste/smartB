# Sprint 3.2: Auto-Seed de Bases Lisas

## Checklist de Implementação

### 1. Schemas & Enums
- [ ] Adicionar BASE_PARENT, BASE_VARIATION aos enums
- [ ] Adicionar PlanOptions com auto_seed_base_plain
- [ ] Adicionar SeedSummary ao response
- [ ] Adicionar autoseed_candidate, included ao PlanItem

### 2. Plan Builder
- [ ] Implementar detect_base_seeds() para encontrar faltantes
- [ ] Gerar BASE_PARENT e BASE_VARIATION candidatos
- [ ] Deduplicar por SKU
- [ ] Atualizar dependências hard/soft conforme toggle
- [ ] Calcular seed_summary

### 3. API
- [ ] Aceitar options no request
- [ ] Passar auto_seed_base_plain ao PlanBuilder

### 4. Frontend
- [ ] Bloco "Bases lisas faltantes detectadas"
- [ ] Toggle para auto_seed_base_plain
- [ ] Regenerar plano ao mudar toggle

## Status
Em progresso...
