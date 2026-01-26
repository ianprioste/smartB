# 🎨 Frontend - smartBling v2

## 📁 Estrutura

```
src/
├── App.jsx                    # Roteamento principal
├── main.jsx                   # Entry point
│
├── hooks/                     # Custom React Hooks
│   ├── useAdmin.js           # CRUD de recursos
│   ├── useWizard.js          # Fluxo do wizard
│   └── useApi.js             # Chamadas HTTP comuns
│
├── components/               # Componentes reutilizáveis
│   ├── Modals.jsx            # Modais genéricos
│   ├── ModelSection.jsx      # Seção de modelos
│   ├── ColorSection.jsx      # Seção de cores
│   └── WizardSteps.jsx       # Steps do wizard
│
├── pages/                    # Páginas/Layouts
│   ├── admin/
│   │   ├── AdminLayout.jsx   # Layout principal
│   │   └── AdminPages.jsx    # Página admin (refatorado)
│   │
│   └── wizard/
│       ├── WizardLayout.jsx  # Layout do wizard
│       └── WizardNew.jsx     # Wizard (refatorado)
│
├── styles/                   # CSS
│   ├── index.css            # Global
│   ├── admin.css            # Admin pages
│   └── wizard.css           # Wizard
│
└── utils/                    # Utilitários
    └── constants.js         # Constantes (URLs, etc)
```

## 🚀 Quick Start

```bash
# Instalar dependências
cd frontend
npm install

# Desenvolver
npm run dev

# Build
npm run build
```

## 🎯 Arquitetura

### Hooks (Reutilizáveis)

#### `useAdmin(resourceType)`
Gerencia estado de recursos (modelos, cores, templates)

```javascript
import { useAdmin } from '@/hooks';

export function ModelsPage() {
  const admin = useAdmin('models');
  
  return (
    <>
      <button onClick={() => admin.startNew()}>Novo</button>
      <table>
        {admin.items.map(item => (
          <tr key={item.id}>
            <td>{item.name}</td>
            <td>
              <button onClick={() => admin.startEdit(item)}>Editar</button>
              <button onClick={() => admin.deleteItem(item.code)}>Deletar</button>
            </td>
          </tr>
        ))}
      </table>
    </>
  );
}
```

#### `useWizard()`
Gerencia fluxo completo do wizard

```javascript
import { useWizard } from '@/hooks';

export function WizardPage() {
  const wizard = useWizard();
  
  function handleNext() {
    if (wizard.validateStep(wizard.step)) {
      wizard.nextStep();
    }
  }
  
  async function handleGeneratePlan() {
    try {
      const plan = await wizard.generatePlan();
      wizard.setPlan(plan);
    } catch (err) {
      wizard.setError(err.message);
    }
  }
  
  return (
    <>
      {wizard.step === 1 && <Step1PrintInfo {...wizard} />}
      {wizard.step === 2 && <Step2Models {...wizard} />}
      {wizard.step === 3 && <Step3Colors {...wizard} />}
    </>
  );
}
```

#### `useApi()`
Chamadas HTTP com erro automático

```javascript
import { useApi } from '@/hooks';

function MyComponent() {
  const api = useApi();
  
  async function loadData() {
    const data = await api.get('/config/models');
    // api.loading, api.error automático
  }
  
  return (
    <>
      {api.loading && <p>Carregando...</p>}
      {api.error && <p>Erro: {api.error}</p>}
    </>
  );
}
```

### Componentes

#### `Modals.jsx`

**ConfirmDeleteModal**
```javascript
<ConfirmDeleteModal
  item={{ code: 'MOD01', name: 'Modelo A' }}
  resourceType="models"
  onConfirm={(code) => deleteModel(code)}
  onCancel={() => setShowModal(false)}
/>
```

**ErrorMessage**
```javascript
<ErrorMessage 
  error={error} 
  onClose={() => setError(null)} 
/>
```

**DataTable**
```javascript
<DataTable
  columns={['Código', 'Nome', 'Tamanhos']}
  rows={models}
  renderCell={(row, col) => {
    if (col === 'Código') return row.code;
    return row[col];
  }}
  onEdit={handleEdit}
  onDelete={handleDelete}
  loading={loading}
/>
```

#### `ModelSection.jsx` & `ColorSection.jsx`

**ModelForm**
```javascript
<ModelForm
  initialData={modelToEdit}
  isEditing={!!modelToEdit}
  onSubmit={handleSave}
  onCancel={() => setEditing(null)}
/>
```

**ModelsPage / ColorsPage**
Componentes prontos para uso:
```javascript
import { ModelsPage } from '@/components';

export default function AdminPage() {
  return <ModelsPage />;
}
```

#### `WizardSteps.jsx`

**Step1PrintInfo**
```javascript
<Step1PrintInfo 
  printInfo={wizard.printInfo}
  setPrintInfo={wizard.setPrintInfo}
  overrides={wizard.overrides}
  setOverrides={wizard.setOverrides}
/>
```

**WizardProgress**
```javascript
<WizardProgress currentStep={wizard.step} />
```

**WizardNavigation**
```javascript
<WizardNavigation
  step={wizard.step}
  canProceed={wizard.validateStep(wizard.step)}
  onPrevious={() => wizard.previousStep()}
  onNext={() => wizard.nextStep()}
  onGeneratePlan={handleGeneratePlan}
  generating={generatingPlan}
/>
```

## 📚 Padrões de Desenvolvimento

### ✅ Use Hooks para Estado

```javascript
// ✅ Correto
function MyPage() {
  const admin = useAdmin('models');
  
  return (
    <>
      {admin.items.map(item => ...)}
    </>
  );
}

// ❌ Evitar
function MyPage() {
  const [items, setItems] = useState([]);
  const [loading, setLoading] = useState(false);
  // ... 100 linhas de useEffect e lógica
}
```

### ✅ Componentes Pequenos e Focados

```javascript
// ✅ Correto (~100-200 linhas)
export function ModelForm({ onSubmit, onCancel }) {
  const [data, setData] = useState({...});
  return <form>...</form>;
}

// ❌ Evitar (~1000+ linhas)
export function AdminPages() {
  // Modelos + Cores + Templates tudo junto
}
```

### ✅ Props Bem Nomeadas

```javascript
// ✅ Correto
<DataTable
  columns={['Nome', 'Email']}
  rows={users}
  onEdit={handleEdit}
  loading={isLoading}
/>

// ❌ Evitar
<DataTable
  cols={...}
  data={...}
  edit={...}
  l={...}
/>
```

## 🧪 Testes

Veja [TESTING.md](../../doc/TESTING.md) para guia de testes.

```bash
# Executar testes
npm test

# Com cobertura
npm test -- --coverage
```

## 📖 Documentação

- [ARCHITECTURE.md](../../doc/ARCHITECTURE.md) - Arquitetura geral
- [API.md](../../doc/API.md) - Endpoints disponíveis
- [TESTING.md](../../doc/TESTING.md) - Testes

## 🔧 Troubleshooting

### Problema: "Cannot find module '@/hooks'"

**Solução:** Adicionar alias em `vite.config.js`:

```javascript
import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';
import path from 'path';

export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: {
      '@': path.resolve(__dirname, './src'),
    },
  },
});
```

### Problema: Hook não atualiza estado

**Solução:** Verificar se está retornando valores de estado, não funções:

```javascript
// ❌ Errado - retorna função
const { items } = useAdmin('models');  // items() ❌

// ✅ Correto - retorna valor
const { items } = useAdmin('models');  // items ✅
```

## 📈 Performance

- ✅ Lazy loading de componentes via `React.lazy()`
- ✅ Memoization de componentes grandes
- ✅ Separação de concerns com hooks
- ✅ CSS modules para estilos locais

## 📞 Contato

Para dúvidas sobre frontend, consulte [ARCHITECTURE.md](../../doc/ARCHITECTURE.md#frontend-structure).
