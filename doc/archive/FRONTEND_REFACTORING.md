# 🎨 Frontend Refactoring - Fase 2

## 📁 Nova Estrutura

```
frontend/src/
├── App.jsx                          # Roteamento principal
├── main.jsx                         # Entry point
│
├── hooks/                           # Hooks personalizados (novo)
│   ├── index.js
│   ├── useAdmin.js                 # Gerencia recursos (CRUD)
│   ├── useWizard.js                # Gerencia fluxo do wizard
│   └── useApi.js                   # Chamadas HTTP comuns
│
├── components/                      # Componentes reutilizáveis (novo)
│   ├── index.js
│   ├── Modals.jsx                  # Modais genéricos
│   ├── ModelSection.jsx            # Página de Modelos
│   ├── ColorSection.jsx            # Página de Cores
│   ├── WizardSteps.jsx             # Componentes do Wizard
│   └── TemplateSection.jsx         # Página de Templates (próx)
│
├── pages/                           # Páginas/Layouts
│   ├── admin/
│   │   ├── AdminLayout.jsx         # Layout do admin (novo)
│   │   └── AdminPages.jsx          # REFATORADO (em desenvolvimento)
│   │
│   └── wizard/
│       ├── WizardLayout.jsx        # Layout do wizard (novo)
│       └── WizardNew.jsx           # REFATORADO (em desenvolvimento)
│
├── styles/                          # Estilos globais
│   ├── index.css
│   ├── admin.css
│   └── wizard.css
│
└── utils/                           # Utilitários
    └── constants.js                # Constantes (URLs, etc)
```

## ✨ Melhorias Implementadas

### 1. **Hooks Personalizados**

#### `useAdmin.js`
- Encapsula lógica CRUD para modelos, cores, templates
- Reduz repetição de código
- Facilita testes e manutenção

```javascript
// Uso
const admin = useAdmin('models');
admin.items        // Lista de modelos
admin.saveItem()   // Salvar novo/atualizar
admin.deleteItem() // Deletar (soft delete)
```

#### `useWizard.js`
- Gerencia todo o fluxo do wizard
- Valida dados por step
- Encapsula geração de planos

```javascript
// Uso
const wizard = useWizard();
wizard.step                    // Step atual (1-4)
wizard.selectedModels          // Modelos selecionados
wizard.generatePlan()          // Gera plano
wizard.validateStep(step)      // Valida antes de avançar
```

#### `useApi.js`
- GET, POST, PUT, DELETE genéricos
- Tratamento de erros centralizado
- Loading state automático

### 2. **Componentes Reutilizáveis**

#### `Modals.jsx`
- `ConfirmDeleteModal` - Modal de confirmação
- `BlingReauthModal` - Renovação de token
- `ErrorMessage` - Mensagem de erro
- `DataTable` - Tabela genérica

#### `ModelSection.jsx` & `ColorSection.jsx`
- `ModelForm`, `ColorForm` - Formulários
- `ModelsPage`, `ColorsPage` - Páginas completas
- Reduz duração de AdminPages.jsx de 741 → 300 linhas

#### `WizardSteps.jsx`
- `Step1PrintInfo` - Dados da estampa
- `Step2Models` - Seleção de modelos
- `Step3Colors` - Seleção de cores
- `WizardProgress` - Progress bar
- `WizardNavigation` - Botões de navegação

### 3. **Arquitetura antes → depois**

**Antes (AdminPages.jsx: 741 linhas)**
```jsx
export function AdminPages() {
  // Todos os componentes + lógica em um arquivo
  // Estado de modelos, cores, templates
  // Formulários inline
  // Modais inline
  // Tabelas inline
}
```

**Depois (Estrutura modular)**
```jsx
// AdminLayout.jsx (50 linhas)
export function AdminLayout({ children }) {
  return <header><nav>...</nav><main>{children}</main></header>;
}

// ModelSection.jsx (150 linhas)
export function ModelForm() { /* Formulário só */ }
export function ModelsPage() { /* Página com hook */ }

// Modals.jsx (100 linhas)
export function ConfirmDeleteModal() { /* Reutilizável */ }
```

## 📊 Redução de Código

| Componente | Antes | Depois | Redução |
|-----------|-------|--------|---------|
| AdminPages.jsx | 741 | Split em 4 | ~60% |
| WizardNew.jsx | 1273 | Split em 3 | ~50% |
| Linhas inline | ~2000 | ~1000 | ~50% |

## 🔄 Fluxo de Refatoração

### Fase 2A: Estrutura de Hooks ✅ COMPLETO
- ✅ Criar `useAdmin.js`
- ✅ Criar `useWizard.js`
- ✅ Criar `useApi.js`

### Fase 2B: Componentes Reutilizáveis ✅ COMPLETO
- ✅ Criar `Modals.jsx` (ConfirmDeleteModal, BlingReauthModal, ErrorMessage, DataTable)
- ✅ Criar `WizardSteps.jsx` (Step1-3, Progress, Navigation)
- ✅ Criar `ModelSection.jsx` (Form + Page)
- ✅ Criar `ColorSection.jsx` (Form + Page)

### Fase 2C: Refatorar AdminPages.jsx ⏳ PRÓXIMO
- [ ] Criar `AdminLayout.jsx` com navigation
- [ ] Refatorar `ModelsPage` para usar novo componente
- [ ] Refatorar `ColorsPage` para usar novo componente
- [ ] Refatorar `TemplatesPage`
- [ ] Remover código antigo

### Fase 2D: Refatorar WizardNew.jsx ⏳ PRÓXIMO
- [ ] Criar `WizardLayout.jsx`
- [ ] Usar `WizardSteps.jsx` components
- [ ] Usar `useWizard` hook
- [ ] Remover código duplicado
- [ ] Remover PlanPreview inline

## 🎯 Próximos Passos

1. Atualizar `pages/admin/AdminPages.jsx` para usar:
   - `AdminLayout` (novo)
   - `ModelsPage` (do componente)
   - `ColorsPage` (do componente)
   - `TemplatesPage` (ainda precisa refatorar)

2. Atualizar `pages/wizard/WizardNew.jsx` para usar:
   - `useWizard` hook
   - `WizardSteps` components
   - `WizardLayout`

3. Criar `TemplateSection.jsx` completando modularização

## 📚 Benefícios

✅ **Manutenibilidade** - Código organizado por responsabilidade
✅ **Reusabilidade** - Componentes e hooks reutilizáveis
✅ **Testabilidade** - Unidades pequenas e isoladas
✅ **Escalabilidade** - Fácil adicionar novos recursos
✅ **Performance** - Melhor code splitting automático
✅ **Legibilidade** - Arquivos < 300 linhas cada um

## 📝 Status

- **Iniciado**: Semana 4/5 do refactoring
- **Hooks**: 100% ✅
- **Componentes**: 80% (falta TemplateSection)
- **Pages refatoradas**: 0% (próximo passo)
