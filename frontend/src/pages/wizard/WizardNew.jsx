import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import '../../styles/wizard.css';

const API_BASE = 'http://localhost:8000';

export function WizardNewPage() {
  const navigate = useNavigate();
  const [step, setStep] = useState(1);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  // Configuration data
  const [models, setModels] = useState([]);
  const [colors, setColors] = useState([]);

  // Form data
  const [printInfo, setPrintInfo] = useState({ code: '', name: '' });
  const [selectedModels, setSelectedModels] = useState([]); // [{code, name, allowed_sizes, selected_sizes}]
  const [selectedColors, setSelectedColors] = useState([]);
  const [overrides, setOverrides] = useState({
    short_description: '',
    complement_description: '',
    complement_same_as_short: true,
    category_override_id: '',
  });

  // Plan data
  const [plan, setPlan] = useState(null);
  const [generatingPlan, setGeneratingPlan] = useState(false);
  const [loadingStatus, setLoadingStatus] = useState('');
  const [showReauthModal, setShowReauthModal] = useState(false);
  const [pendingRetryAfterReauth, setPendingRetryAfterReauth] = useState(false);
  const [seedResultsModal, setSeedResultsModal] = useState(null);
  const [executionResultsModal, setExecutionResultsModal] = useState(null);

  useEffect(() => {
    fetchConfiguration();
  }, []);

  async function fetchConfiguration() {
    try {
      setLoading(true);
      const [modelsResp, colorsResp] = await Promise.all([
        fetch(`${API_BASE}/config/models`),
        fetch(`${API_BASE}/config/colors`),
      ]);

      if (!modelsResp.ok || !colorsResp.ok) {
        throw new Error('Failed to fetch configuration');
      }

      const modelsData = await modelsResp.json();
      const colorsData = await colorsResp.json();

      console.log('Models data:', modelsData);
      console.log('Colors data:', colorsData);

      const activeModels = modelsData.filter(m => m.is_active);
      const activeColors = colorsData.filter(c => c.is_active);
      
      console.log('Active models:', activeModels);
      console.log('Active colors:', activeColors);

      setModels(activeModels);
      setColors(activeColors);
    } catch (err) {
      console.error('Error fetching configuration:', err);
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }

  function handleModelToggle(model) {
    const isSelected = selectedModels.find(m => m.code === model.code);
    if (isSelected) {
      setSelectedModels(selectedModels.filter(m => m.code !== model.code));
    } else {
      setSelectedModels([
        ...selectedModels,
        {
          code: model.code,
          name: model.name,
          allowed_sizes: model.allowed_sizes,
          selected_sizes: [...model.allowed_sizes], // Start with all sizes selected
          price: '',
        },
      ]);
    }
  }

  function handleSizeToggle(modelCode, size) {
    setSelectedModels(
      selectedModels.map(m => {
        if (m.code === modelCode) {
          const isSelected = m.selected_sizes.includes(size);
          return {
            ...m,
            selected_sizes: isSelected
              ? m.selected_sizes.filter(s => s !== size)
              : [...m.selected_sizes, size],
          };
        }
        return m;
      })
    );
  }

  function handlePriceChange(modelCode, value) {
    setSelectedModels(
      selectedModels.map(m =>
        m.code === modelCode
          ? { ...m, price: value }
          : m
      )
    );
  }

  function handleColorToggle(colorCode) {
    if (selectedColors.includes(colorCode)) {
      setSelectedColors(selectedColors.filter(c => c !== colorCode));
    } else {
      setSelectedColors([...selectedColors, colorCode]);
    }
  }

  async function generatePlanRequest(autoSeedBasePlain = false) {
    const payload = {
      print: {
        code: printInfo.code.toUpperCase(),
        name: printInfo.name,
      },
      models: selectedModels.map(m => ({
        code: m.code,
        sizes: m.selected_sizes,
        price: parseFloat(m.price),
      })),
      colors: selectedColors,
      overrides: {
        short_description: overrides.short_description || null,
        complement_description: overrides.complement_same_as_short
          ? null
          : overrides.complement_description || null,
        complement_same_as_short: overrides.complement_same_as_short,
        category_override_id: overrides.category_override_id
          ? parseInt(overrides.category_override_id, 10)
          : null,
      },
      options: {
        auto_seed_base_plain: autoSeedBasePlain,
      },
    };

    const resp = await fetch(`${API_BASE}/plans/new`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    });

    if (!resp.ok) {
      const errorData = await resp.json();
      
      // Check for token expiration
      if (resp.status === 401 && errorData.detail?.code === 'BLING_TOKEN_EXPIRED') {
        const error = new Error('Token expirado');
        error.code = 'BLING_TOKEN_EXPIRED';
        error.status = 401;
        throw error;
      }
      
      throw new Error(errorData.detail?.message || 'Falha ao gerar plano');
    }

    return await resp.json();
  }

  async function handleGeneratePlan() {
    if (!printInfo.code || !printInfo.name) {
      setError('Preencha código e nome da estampa');
      return;
    }

    if (selectedModels.length === 0) {
      setError('Selecione pelo menos um modelo');
      return;
    }

    for (const model of selectedModels) {
      const parsedPrice = parseFloat(model.price);
      if (!parsedPrice || parsedPrice <= 0) {
        setError(`Informe preço válido para o modelo ${model.code}`);
        return;
      }
    }

    if (selectedColors.length === 0) {
      setError('Selecione pelo menos uma cor');
      return;
    }

    // Validate that all models have at least one size
    for (const model of selectedModels) {
      if (model.selected_sizes.length === 0) {
        setError(`Modelo ${model.code} não tem tamanhos selecionados`);
        return;
      }
    }

    try {
      setGeneratingPlan(true);
      setError(null);
      setLoadingStatus('📋 Validando dados...');

      await new Promise(resolve => setTimeout(resolve, 300));
      setLoadingStatus('🔍 Buscando templates configurados...');

      await new Promise(resolve => setTimeout(resolve, 300));
      setLoadingStatus('🎨 Calculando SKUs e variações...');

      setLoadingStatus('⚙️ Gerando plano no servidor...');
      const planData = await generatePlanRequest(false);

      setLoadingStatus('📦 Processando itens do plano...');
      
      await new Promise(resolve => setTimeout(resolve, 300));
      setLoadingStatus('✅ Plano gerado com sucesso!');
      
      await new Promise(resolve => setTimeout(resolve, 500));
      setPlan(planData);
      setStep(4); // Go to preview
    } catch (err) {
      // Check if token expired
      if (err.code === 'BLING_TOKEN_EXPIRED') {
        setShowReauthModal(true);
        setPendingRetryAfterReauth(true);
        setError('Token expirado. Renove o token para continuar.');
      } else {
        setError(err.message || 'Erro ao gerar plano');
      }
    } finally {
      setGeneratingPlan(false);
      setLoadingStatus('');
    }
  }

  function canProceed() {
    switch (step) {
      case 1:
        return printInfo.code && printInfo.name;
      case 2:
        return (
          selectedModels.length > 0 &&
          selectedModels.every(m => m.selected_sizes.length > 0 && parseFloat(m.price) > 0)
        );
      case 3:
        return selectedColors.length > 0;
      default:
        return false;
    }
  }

  if (loading) {
    return (
      <div className="wizard-container">
        <div className="wizard-loading">Carregando configuração...</div>
      </div>
    );
  }

  return (
    <div className="wizard-container">
      <header className="wizard-header">
        <h1>🪄 Assistente de Novo Cadastro</h1>
        <button className="btn-secondary" onClick={() => navigate('/admin/models')}>
          ← Voltar
        </button>
      </header>

      <div className="wizard-progress">
        <div className={`wizard-step ${step >= 1 ? 'active' : ''} ${step > 1 ? 'completed' : ''}`}>
          1. Estampa
        </div>
        <div className={`wizard-step ${step >= 2 ? 'active' : ''} ${step > 2 ? 'completed' : ''}`}>
          2. Modelos
        </div>
        <div className={`wizard-step ${step >= 3 ? 'active' : ''} ${step > 3 ? 'completed' : ''}`}>
          3. Cores
        </div>
        <div className={`wizard-step ${step >= 4 ? 'active' : ''}`}>4. Preview</div>
      </div>

      {generatingPlan && (
        <div className="loading-modal-overlay">
          <div className="loading-modal">
            <div className="loading-spinner"></div>
            <h2>{loadingStatus}</h2>
            <p>Por favor, aguarde...</p>
          </div>
        </div>
      )}

      {error && (
        <div className="wizard-error">
          ⚠️ {error}
          <button onClick={() => setError(null)}>×</button>
        </div>
      )}

      {/* Step 1: Print Info */}
      {step === 1 && (
        <div className="wizard-content">
          <h2>📝 Dados da Estampa</h2>
          <div className="form-group">
            <label>Código da Estampa *</label>
            <input
              type="text"
              value={printInfo.code}
              onChange={e => setPrintInfo({ ...printInfo, code: e.target.value.toUpperCase() })}
              placeholder="Ex: STPV"
              maxLength={20}
            />
          </div>
          <div className="form-group">
            <label>Nome da Estampa *</label>
            <input
              type="text"
              value={printInfo.name}
              onChange={e => setPrintInfo({ ...printInfo, name: e.target.value })}
              placeholder="Ex: Santa Teresinha Pequena Via"
            />
          </div>
          <div className="form-grid">
            <div className="form-group">
              <label>Descrição Curta (opcional)</label>
              <textarea
                value={overrides.short_description}
                onChange={e => setOverrides({ ...overrides, short_description: e.target.value })}
                placeholder="Ex: Santa Teresinha | Camiseta | Marca"
                rows={2}
              />
            </div>
            <div className="form-group">
              <label>
                <input
                  type="checkbox"
                  checked={overrides.complement_same_as_short}
                  onChange={e =>
                    setOverrides({
                      ...overrides,
                      complement_same_as_short: e.target.checked,
                      // If toggled on, clear manual complement to avoid confusion
                      ...(e.target.checked ? { complement_description: '' } : {}),
                    })
                  }
                />{' '}
                Usar descrição curta também como complementar
              </label>
              {!overrides.complement_same_as_short && (
                <textarea
                  value={overrides.complement_description}
                  onChange={e => setOverrides({ ...overrides, complement_description: e.target.value })}
                  placeholder="Descrição complementar"
                  rows={2}
                />
              )}
            </div>
            <div className="form-group">
              <label>Categoria (ID) opcional</label>
              <input
                type="number"
                value={overrides.category_override_id}
                onChange={e => setOverrides({ ...overrides, category_override_id: e.target.value })}
                placeholder="ID da categoria no Bling"
                min="0"
              />
              <small>Deixe em branco para manter a categoria do template</small>
            </div>
          </div>
        </div>
      )}

      {/* Step 2: Models */}
      {step === 2 && (
        <div className="wizard-content">
          <h2>📐 Selecione os Modelos e Tamanhos</h2>
          {models.length === 0 ? (
            <div className="wizard-error">
              ⚠️ Nenhum modelo disponível. Por favor, crie modelos primeiro.
            </div>
          ) : (
            <div className="models-grid">
              {models.map(model => {
                const selected = selectedModels.find(m => m.code === model.code);
                return (
                  <div key={model.code} className={`model-card ${selected ? 'selected' : ''}`}>
                    <div className="model-header" onClick={() => handleModelToggle(model)}>
                      <input type="checkbox" checked={!!selected} readOnly />
                      <strong>{model.code}</strong> - {model.name}
                    </div>
                    {selected && (
                      <div className="sizes-selection">
                        <label>Tamanhos:</label>
                        <div className="sizes-buttons">
                          {model.allowed_sizes.map(size => (
                            <button
                              key={size}
                              className={`size-btn ${
                                selected.selected_sizes.includes(size) ? 'active' : ''
                              }`}
                              onClick={() => handleSizeToggle(model.code, size)}
                            >
                              {size}
                            </button>
                          ))}
                        </div>
                        <div className="form-group inline">
                          <label>Preço (R$)</label>
                          <input
                            type="number"
                            step="0.01"
                            min="0"
                            value={selected.price}
                            onClick={e => e.stopPropagation()}
                            onChange={e => handlePriceChange(model.code, e.target.value)}
                            placeholder="Ex: 79.90"
                          />
                        </div>
                      </div>
                    )}
                  </div>
                );
              })}
            </div>
          )}
        </div>
      )}

      {/* Step 3: Colors */}
      {step === 3 && (
        <div className="wizard-content">
          <h2>🎨 Selecione as Cores</h2>
          <div className="colors-grid">
            {colors.map(color => (
              <div
                key={color.code}
                className={`color-card ${selectedColors.includes(color.code) ? 'selected' : ''}`}
                onClick={() => handleColorToggle(color.code)}
              >
                <input type="checkbox" checked={selectedColors.includes(color.code)} readOnly />
                <strong>{color.code}</strong> - {color.name}
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Step 4: Preview */}
      {step === 4 && plan && (
        <PlanPreview
          plan={plan}
          onBack={() => setStep(3)}
          onExecute={async (currentPlan) => {
            try {
              setLoadingStatus('Executando plano no Bling...');
              setGeneratingPlan(true);
              const response = await fetch('/api/plans/execute', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(currentPlan),
              });
              
              if (!response.ok) {
                const error = await response.json();
                throw new Error(error.detail || 'Erro ao executar plano');
              }
              
              const result = await response.json();
              setLoadingStatus('');
              setGeneratingPlan(false);
              setExecutionResultsModal(result);
            } catch (error) {
              setLoadingStatus('');
              setGeneratingPlan(false);
              alert(`❌ Erro ao executar: ${error.message}`);
            }
          }}
          onRegeneratePlan={async (autoSeed) => {
            return await generatePlanRequest(autoSeed);
          }}
          onShowReauthModal={() => setShowReauthModal(true)}
          onSetPendingRetry={(value) => setPendingRetryAfterReauth(value)}
          onSetError={(msg) => setError(msg)}
        />
      )}

      {/* Navigation */}
      {step < 4 && (
        <div className="wizard-actions">
          {step > 1 && (
            <button className="btn-secondary" onClick={() => setStep(step - 1)}>
              ← Anterior
            </button>
          )}
          {step < 3 && (
            <button
              className="btn-primary"
              onClick={() => setStep(step + 1)}
              disabled={!canProceed()}
            >
              Próximo →
            </button>
          )}
          {step === 3 && (
            <button
              className="btn-primary"
              onClick={handleGeneratePlan}
              disabled={!canProceed() || generatingPlan}
            >
              {generatingPlan ? 'Gerando Preview...' : '🔍 Gerar Preview'}
            </button>
          )}
        </div>
      )}

      {/* Modal de reautenticação */}
      {showReauthModal && (
        <div className="modal-overlay">
          <div className="modal">
            <h3>🔑 Token do Bling Expirado</h3>
            <p>O token de acesso ao Bling expirou e precisa ser renovado.</p>
            <p style={{ marginTop: '16px', fontSize: '0.95rem', color: '#666' }}>
              Ao clicar em "Renovar Token", você será redirecionado para o Bling para autorizar novamente.
              Após autorizar, você será redirecionado de volta.
            </p>
            <div className="modal-actions">
              <button 
                onClick={() => {
                  setShowReauthModal(false);
                  setPendingRetryAfterReauth(false);
                  setError(null);
                }} 
                style={{ background: '#64748b' }}
              >
                Cancelar
              </button>
              {!pendingRetryAfterReauth && (
                <button 
                  onClick={() => {
                    window.open('http://localhost:8000/auth/bling/connect', '_blank');
                    setPendingRetryAfterReauth(true);
                    setError('Autenticando no Bling... Aguarde até completar a autenticação.');
                    
                    // Auto-detect when user returns and auto-retry
                    const handleFocus = () => {
                      setTimeout(() => {
                        setShowReauthModal(false);
                        setPendingRetryAfterReauth(false);
                        setError(null);
                        handleGeneratePlan();
                      }, 2000);
                      window.removeEventListener('focus', handleFocus);
                    };
                    window.addEventListener('focus', handleFocus);
                  }}
                  style={{ background: '#4CAF50' }}
                >
                  🔄 Renovar Token Agora
                </button>
              )}
              {pendingRetryAfterReauth && (
                <button 
                  onClick={() => {
                    setShowReauthModal(false);
                    setPendingRetryAfterReauth(false);
                    setError(null);
                    // Retry generating the plan
                    handleGeneratePlan();
                  }}
                  style={{ background: '#3b82f6' }}
                >
                  ✅ Tentar Novamente
                </button>
              )}
            </div>
          </div>
        </div>
      )}
      
      {seedResultsModal && (
        <SeedResultsModal 
          results={seedResultsModal} 
          onClose={() => setSeedResultsModal(null)} 
        />
      )}
      
      {executionResultsModal && (
        <ExecutionResultsModal 
          results={executionResultsModal} 
          onClose={() => setExecutionResultsModal(null)} 
        />
      )}
    </div>
  );
}

function PlanPreview({ plan: initialPlan, onBack, onExecute, onRegeneratePlan, onShowReauthModal, onSetPendingRetry, onSetError }) {
  const [plan, setPlan] = React.useState(initialPlan);
  const [autoSeedBasePlain, setAutoSeedBasePlain] = React.useState(initialPlan.options?.auto_seed_base_plain || false);
  const [isRegenerating, setIsRegenerating] = React.useState(false);
  const [loadingStatus, setLoadingStatus] = React.useState('');
  const [seedResultsModal, setSeedResultsModal] = React.useState(null);
  const [includeExistingProducts, setIncludeExistingProducts] = React.useState(false);

  async function handleToggleAutoSeed(newValue) {
    setAutoSeedBasePlain(newValue);
    setIsRegenerating(true);
    
    try {
      if (newValue) {
        setLoadingStatus('🌱 Ativando auto-seed de bases lisas...');
      } else {
        setLoadingStatus('🔄 Desativando auto-seed de bases lisas...');
      }
      await new Promise(resolve => setTimeout(resolve, 300));
      
      setLoadingStatus('⚙️ Recalculando plano no servidor...');
      const newPlan = await onRegeneratePlan(newValue);
      
      await new Promise(resolve => setTimeout(resolve, 300));
      setLoadingStatus('✅ Plano regenerado com sucesso!');
      
      await new Promise(resolve => setTimeout(resolve, 500));
      setPlan(newPlan);
    } catch (err) {
      alert(`Erro ao regenerar plano: ${err.message}`);
      setAutoSeedBasePlain(!newValue);
    } finally {
      setIsRegenerating(false);
      setLoadingStatus('');
    }
  }

  async function handleRecalculate() {
    setIsRegenerating(true);
    
    try {
      setLoadingStatus('🔍 Verificando cadastros no Bling...');
      await new Promise(resolve => setTimeout(resolve, 300));
      
      setLoadingStatus('⚙️ Recalculando plano...');
      // Recalculate with current auto_seed setting to check if user created items manually
      const newPlan = await onRegeneratePlan(autoSeedBasePlain);
      
      await new Promise(resolve => setTimeout(resolve, 300));
      setLoadingStatus('✅ Plano atualizado!');
      
      await new Promise(resolve => setTimeout(resolve, 500));
      setPlan(newPlan);
    } catch (err) {
      alert(`Erro ao recalcular plano: ${err.message}`);
    } finally {
      setIsRegenerating(false);
      setLoadingStatus('');
    }
  }

  async function handleSeedBases() {
    setIsRegenerating(true);
    try {
      setLoadingStatus('🌱 Criando bases lisas faltantes...');
      await new Promise(resolve => setTimeout(resolve, 200));

      const response = await fetch('/api/plans/seed-bases', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(plan),
      });

      if (!response.ok) {
        const error = await response.json().catch(() => ({}));
        
        // Check for token expiration
        if (response.status === 401 && error.detail?.code === 'BLING_TOKEN_EXPIRED') {
          onShowReauthModal();
          onSetPendingRetry(true);
          onSetError('Token expirado. Renove o token para continuar.');
          setIsRegenerating(false);
          setLoadingStatus('');
          return;
        }
        
        throw new Error(error.detail || 'Erro ao criar bases lisas');
      }

      const result = await response.json();
      
      // Show results modal
      setSeedResultsModal(result);
      
      // Recalcula o plano para desbloquear dependências
      setLoadingStatus('🔄 Recalculando plano após criação...');
      await new Promise(resolve => setTimeout(resolve, 300));
      const newPlan = await onRegeneratePlan(false);
      setPlan(newPlan);
      setLoadingStatus('✅ Plano atualizado!');
      await new Promise(resolve => setTimeout(resolve, 400));
    } catch (err) {
      alert(`❌ Erro ao criar bases lisas: ${err.message}`);
    } finally {
      setIsRegenerating(false);
      setLoadingStatus('');
    }
  }

  const hasBlockers = plan.has_blockers;

  // Group items by action
  const itemsByAction = {
    CREATE: plan.items.filter(i => i.action === 'CREATE'),
    UPDATE: plan.items.filter(i => i.action === 'UPDATE'),
    NOOP: plan.items.filter(i => i.action === 'NOOP'),
    BLOCKED: plan.items.filter(i => i.action === 'BLOCKED'),
  };

  function getPlanForExecution() {
    if (includeExistingProducts) {
      // Convert NOOP items to CREATE/UPDATE
      return {
        ...plan,
        items: plan.items.map(item => {
          if (item.action === 'NOOP') {
            // Mark NOOP items as CREATE so they get processed
            return { ...item, action: 'CREATE' };
          }
          return item;
        })
      };
    }
    return plan;
  }

  return (
    <div className="wizard-content preview-content">
      {isRegenerating && (
        <div className="loading-modal-overlay">
          <div className="loading-modal">
            <div className="loading-spinner"></div>
            <h2>{loadingStatus}</h2>
            <p>Por favor, aguarde...</p>
          </div>
        </div>
      )}

      <h2>📊 Preview do Plano</h2>

      <div className="plan-summary">
        <div className="summary-card">
          <strong>{plan.summary.models}</strong>
          <span>Modelos</span>
        </div>
        <div className="summary-card">
          <strong>{plan.summary.colors}</strong>
          <span>Cores</span>
        </div>
        <div className="summary-card">
          <strong>{plan.summary.total_skus}</strong>
          <span>Total SKUs</span>
        </div>
        <div className="summary-card status-create">
          <strong>{plan.summary.create_count}</strong>
          <span>🟢 Criar</span>
        </div>
        <div className="summary-card status-update">
          <strong>{plan.summary.update_count}</strong>
          <span>🟡 Atualizar</span>
        </div>
        <div className="summary-card status-noop">
          <strong>{plan.summary.noop_count}</strong>
          <span>🔵 Sem mudança</span>
        </div>
        <div className="summary-card status-blocked">
          <strong>{plan.summary.blocked_count}</strong>
          <span>🔴 Bloqueado</span>
        </div>
      </div>

      {plan.seed_summary && (plan.seed_summary.base_parent_missing.length > 0 || plan.seed_summary.base_variation_missing.length > 0) && (
        <div className="seed-summary-block">
          <h3>🔍 Bases Lisas Faltantes Detectadas</h3>
          
          {plan.seed_summary.base_parent_missing.length > 0 && (
            <div className="seed-section">
              <strong>Base Parents ({plan.seed_summary.base_parent_missing.length}):</strong>
              <div className="seed-list">
                {plan.seed_summary.base_parent_missing.slice(0, 5).map(sku => (
                  <code key={sku}>{sku}</code>
                ))}
                {plan.seed_summary.base_parent_missing.length > 5 && (
                  <code className="seed-more">+{plan.seed_summary.base_parent_missing.length - 5} mais</code>
                )}
              </div>
            </div>
          )}
          
          {plan.seed_summary.base_variation_missing.length > 0 && (
            <div className="seed-section">
              <strong>Base Variations ({plan.seed_summary.base_variation_missing.length}):</strong>
              <div className="seed-list">
                {plan.seed_summary.base_variation_missing.slice(0, 5).map(sku => (
                  <code key={sku}>{sku}</code>
                ))}
                {plan.seed_summary.base_variation_missing.length > 5 && (
                  <code className="seed-more">+{plan.seed_summary.base_variation_missing.length - 5} mais</code>
                )}
              </div>
            </div>
          )}
          
          <div className="seed-actions-simple">
            <div className="seed-toggle">
              <button
                className="btn-primary"
                onClick={handleSeedBases}
                disabled={isRegenerating}
              >
                🌱 Criar bases lisas faltantes
              </button>
            </div>
            
            <div className="seed-manual-hint">
              <p>💡 <strong>Ou cadastre manualmente no Bling</strong> e clique em Recalcular para verificar</p>
              <button
                className="btn-secondary"
                onClick={handleRecalculate}
                disabled={isRegenerating}
              >
                🔄 Recalcular Plano
              </button>
            </div>
          </div>
        </div>
      )}

      {hasBlockers && (
        <div className="blocker-warning">
          ⚠️ <strong>Existem bloqueios!</strong> Corrija Templates antes de continuar.
        </div>
      )}

      {itemsByAction.NOOP.length > 0 && (
        <div className="noop-option-block">
          <div className="noop-checkbox">
            <input 
              type="checkbox" 
              id="includeExisting" 
              checked={includeExistingProducts}
              onChange={(e) => setIncludeExistingProducts(e.target.checked)}
            />
            <label htmlFor="includeExisting">
              <strong>♻️ Também atualizar produtos existentes ({itemsByAction.NOOP.length})</strong>
              <br />
              <small>Marcados com "🔵 Sem mudança" serão atualizados com os dados atuais do plano</small>
            </label>
          </div>
        </div>
      )}

      <div className="plan-table-container">
        <table className="plan-table">
          <thead>
            <tr>
              <th>SKU</th>
              <th>Tipo</th>
              <th>Ação</th>
              <th>Preço</th>
              <th>Desc. Curta</th>
              <th>Dependências</th>
              <th>Template</th>
              <th>Motivo</th>
            </tr>
          </thead>
          <tbody>
            {plan.items.map((item, idx) => (
              <tr key={idx} className={`status-${item.action.toLowerCase()}`}>
                <td>
                  <code>{item.sku}</code>
                </td>
                <td>{
                  item.entity === 'BASE_PLAIN' ? 'Base Lisa' :
                  item.entity === 'PARENT_PRINTED' ? 'Principal Estampado' :
                  item.entity === 'VARIATION_PRINTED' ? 'Variação Estampada' :
                  item.entity
                }</td>
                <td>
                  <span className={`badge badge-${item.action.toLowerCase()}`}>
                    {item.action === 'CREATE' && 'Criar'}
                    {item.action === 'UPDATE' && 'Atualizar'}
                    {item.action === 'NOOP' && 'OK'}
                    {item.action === 'BLOCKED' && 'Bloqueado'}
                  </span>
                </td>
                <td>
                  {item.computed_payload_preview?.preco ?? item.overrides_used?.price ?? '-'}
                </td>
                <td className="desc-cell">
                  {item.computed_payload_preview?.descricaoCurta || '-'}
                </td>
                <td>
                  {(item.hard_dependencies?.length || item.soft_dependencies?.length) ? (
                    <div className="dependencies">
                      {item.hard_dependencies?.map(dep => (
                        <code key={dep} className="dep-hard">{dep}</code>
                      ))}
                      {item.soft_dependencies?.map(dep => (
                        <code key={dep} className="dep-soft">{dep}</code>
                      ))}
                    </div>
                  ) : (
                    '-'
                  )}
                </td>
                <td>
                  {item.template ? (
                    <span>
                      {item.template.model} / {
                        item.template.kind === 'BASE_PLAIN' ? 'Base Lisa' :
                        item.template.kind === 'PARENT_PRINTED' ? 'Principal Estampado' :
                        item.template.kind === 'VARIATION_PRINTED' ? 'Variação Estampada' :
                        item.template.kind
                      }
                    </span>
                  ) : (
                    '-'
                  )}
                </td>
                <td>
                  <div className="motivo-cell">
                    {item.reason === 'MANUALLY_CREATED' ? (
                      <div className="warning-item">ℹ️ Criado manualmente no Bling</div>
                    ) : item.reason === 'AUTO_SEED' ? (
                      <div className="warning-item">🌱 Base criada automaticamente para garantir integridade</div>
                    ) : item.reason === 'MISSING_TEMPLATE_PAYLOAD' ? (
                      <div className="warning-item blocked-reason">
                        🚫 Template sem payload - não pode executar. Configure no Bling.
                      </div>
                    ) : item.reason ? (
                      <div className="reason-tag">{item.reason}</div>
                    ) : null}
                    {item.diff_summary && item.diff_summary.length > 0 && (
                      <div className="diff-summary">
                        {item.diff_summary.map(field => (
                          <span key={field} className="diff-field">{field}</span>
                        ))}
                      </div>
                    )}
                    {item.warnings && item.warnings.length > 0 && (
                      <div className="warnings">
                        {item.warnings.map((warn, idx) => (
                          <div key={idx} className="warning-item">⚠️ {warn}</div>
                        ))}
                      </div>
                    )}
                    {!item.reason && !item.diff_summary?.length && !item.warnings?.length && (
                      <span>{item.message || '-'}</span>
                    )}
                  </div>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <div className="wizard-actions">
        <button className="btn-secondary" onClick={onBack}>
          ← Voltar
        </button>
        <button 
          className="btn-secondary" 
          onClick={() => {
            window.open('http://localhost:8000/auth/bling/connect', '_blank');
            alert('🔄 Janela de autenticação aberta. Complete a autenticação e depois retorne.');
          }}
          style={{ background: '#f59e0b', color: 'white' }}
        >
          🔑 Renovar Token Bling
        </button>
        <button className="btn-primary" onClick={() => onExecute(getPlanForExecution())} disabled={hasBlockers}>
          {hasBlockers ? '🚫 Bloqueado' : '✅ Executar no Bling'}
        </button>
      </div>
      
      {seedResultsModal && (
        <SeedResultsModal 
          results={seedResultsModal} 
          onClose={() => setSeedResultsModal(null)} 
        />
      )}
    </div>
  );
}

function SeedResultsModal({ results, onClose }) {
  if (!results) return null;

  const { summary, results: items } = results;
  const createdItems = items.filter(r => r.status === 'created');
  const updatedItems = items.filter(r => r.status === 'updated');
  const failedItems = items.filter(r => r.status === 'failed');

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal" onClick={(e) => e.stopPropagation()} style={{ maxWidth: '600px' }}>
        <h3>✅ Bases Criadas</h3>
        
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr 1fr', gap: '12px', marginBottom: '20px' }}>
          <div style={{ background: '#f0fdf4', border: '1px solid #86efac', borderRadius: '8px', padding: '14px', textAlign: 'center' }}>
            <div style={{ fontSize: '22px', fontWeight: 'bold', color: '#16a34a' }}>
              {summary.created_products || 0}
            </div>
            <div style={{ color: '#15803d', marginTop: '2px', fontSize: '12px' }}>
              Criados
            </div>
          </div>
          
          <div style={{ background: '#eff6ff', border: '1px solid #93c5fd', borderRadius: '8px', padding: '14px', textAlign: 'center' }}>
            <div style={{ fontSize: '22px', fontWeight: 'bold', color: '#2563eb' }}>
              {summary.updated_products || 0}
            </div>
            <div style={{ color: '#1e40af', marginTop: '2px', fontSize: '12px' }}>
              Atualizados
            </div>
          </div>
          
          <div style={{ background: '#fef3c7', border: '1px solid #fcd34d', borderRadius: '8px', padding: '14px', textAlign: 'center' }}>
            <div style={{ fontSize: '22px', fontWeight: 'bold', color: '#d97706' }}>
              {summary.created_variations || 0}
            </div>
            <div style={{ color: '#b45309', marginTop: '2px', fontSize: '12px' }}>
              Variações
            </div>
          </div>
          
          <div style={{ background: '#fef3c7', border: '1px solid #fcd34d', borderRadius: '8px', padding: '14px', textAlign: 'center' }}>
            <div style={{ fontSize: '22px', fontWeight: 'bold', color: '#d97706' }}>
              {summary.total_items}
            </div>
            <div style={{ color: '#b45309', marginTop: '4px', fontSize: '13px' }}>
              Total
            </div>
          </div>
        </div>

        {createdItems.length > 0 && (
          <div style={{ marginBottom: '20px' }}>
            <h4 style={{ marginBottom: '12px', color: '#059669' }}>Produtos Criados:</h4>
            <div style={{ maxHeight: '300px', overflowY: 'auto' }}>
              {createdItems.map((item, idx) => (
                <div 
                  key={idx} 
                  style={{
                    padding: '12px',
                    background: '#f9fafb',
                    border: '1px solid #e5e7eb',
                    borderRadius: '6px',
                    marginBottom: '8px'
                  }}
                >
                  <div style={{ fontWeight: '600', marginBottom: '4px' }}>{item.sku}</div>
                  <div style={{ fontSize: '13px', color: '#6b7280' }}>
                    ID: {item.id}
                    {item.variations_count > 0 && ` • ${item.variations_count} variações`}
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}

        {updatedItems.length > 0 && (
          <div style={{ marginBottom: '20px' }}>
            <h4 style={{ marginBottom: '12px', color: '#2563eb' }}>Produtos Atualizados:</h4>
            <div style={{ maxHeight: '300px', overflowY: 'auto' }}>
              {updatedItems.map((item, idx) => (
                <div 
                  key={idx} 
                  style={{
                    padding: '12px',
                    background: '#f9fafb',
                    border: '1px solid #e5e7eb',
                    borderRadius: '6px',
                    marginBottom: '8px'
                  }}
                >
                  <div style={{ fontWeight: '600', marginBottom: '4px' }}>{item.sku}</div>
                  <div style={{ fontSize: '13px', color: '#6b7280' }}>
                    ID: {item.id}
                    {item.variations_count > 0 && ` • ${item.variations_count} variações adicionadas`}
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}

        {failedItems.length > 0 && (
          <div style={{ marginBottom: '20px' }}>
            <h4 style={{ marginBottom: '12px', color: '#dc2626' }}>Falhas:</h4>
            {failedItems.map((item, idx) => (
              <div key={idx} style={{ padding: '8px', color: '#dc2626' }}>
                • {item.sku}
              </div>
            ))}
          </div>
        )}

        <div className="modal-actions">
          <button onClick={onClose} style={{ width: '100%' }}>
            Fechar
          </button>
        </div>
      </div>
    </div>
  );
}

function ExecutionResultsModal({ results, onClose }) {
  if (!results) return null;

  const { summary, results: items } = results;
  const successItems = items.filter(r => r.status === 'success');
  const failedItems = items.filter(r => r.status === 'failed');
  
  const createdItems = successItems.filter(r => r.action === 'CREATE');
  const updatedItems = successItems.filter(r => r.action === 'UPDATE');

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal" onClick={(e) => e.stopPropagation()} style={{ maxWidth: '700px' }}>
        <h3>✅ Plano Executado com Sucesso</h3>
        
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(5, 1fr)', gap: '10px', marginBottom: '20px' }}>
          <div style={{ background: '#f0fdf4', border: '1px solid #86efac', borderRadius: '8px', padding: '12px', textAlign: 'center' }}>
            <div style={{ fontSize: '20px', fontWeight: 'bold', color: '#16a34a' }}>
              {summary.created_parents || 0}
            </div>
            <div style={{ color: '#15803d', marginTop: '2px', fontSize: '11px' }}>
              Pais
            </div>
          </div>
          
          <div style={{ background: '#eff6ff', border: '1px solid #93c5fd', borderRadius: '8px', padding: '12px', textAlign: 'center' }}>
            <div style={{ fontSize: '20px', fontWeight: 'bold', color: '#2563eb' }}>
              {summary.created_variations || 0}
            </div>
            <div style={{ color: '#1e40af', marginTop: '2px', fontSize: '11px' }}>
              Variações
            </div>
          </div>
          
          <div style={{ background: '#fef3c7', border: '1px solid #fcd34d', borderRadius: '8px', padding: '12px', textAlign: 'center' }}>
            <div style={{ fontSize: '20px', fontWeight: 'bold', color: '#d97706' }}>
              {summary.created_bases || 0}
            </div>
            <div style={{ color: '#b45309', marginTop: '2px', fontSize: '11px' }}>
              Bases
            </div>
          </div>
          
          <div style={{ background: '#f3e8ff', border: '1px solid #c084fc', borderRadius: '8px', padding: '12px', textAlign: 'center' }}>
            <div style={{ fontSize: '20px', fontWeight: 'bold', color: '#9333ea' }}>
              {updatedItems.length}
            </div>
            <div style={{ color: '#7e22ce', marginTop: '2px', fontSize: '11px' }}>
              Atualizados
            </div>
          </div>
          
          <div style={{ background: failedItems.length > 0 ? '#fef2f2' : '#f9fafb', border: failedItems.length > 0 ? '1px solid #fca5a5' : '1px solid #e5e7eb', borderRadius: '8px', padding: '12px', textAlign: 'center' }}>
            <div style={{ fontSize: '20px', fontWeight: 'bold', color: failedItems.length > 0 ? '#dc2626' : '#6b7280' }}>
              {failedItems.length}
            </div>
            <div style={{ color: failedItems.length > 0 ? '#b91c1c' : '#6b7280', marginTop: '2px', fontSize: '11px' }}>
              Falhas
            </div>
          </div>
        </div>

        {createdItems.length > 0 && (
          <div style={{ marginBottom: '20px' }}>
            <h4 style={{ marginBottom: '12px', color: '#059669' }}>✓ Criados ({createdItems.length}):</h4>
            <div style={{ maxHeight: '200px', overflowY: 'auto' }}>
              {createdItems.map((item, idx) => (
                <div 
                  key={idx} 
                  style={{
                    padding: '10px 12px',
                    background: '#f9fafb',
                    border: '1px solid #e5e7eb',
                    borderRadius: '6px',
                    marginBottom: '6px',
                    display: 'flex',
                    justifyContent: 'space-between',
                    alignItems: 'center'
                  }}
                >
                  <div>
                    <span style={{ fontWeight: '600' }}>{item.sku}</span>
                    <span style={{ fontSize: '12px', color: '#6b7280', marginLeft: '8px' }}>
                      {item.entity}
                    </span>
                  </div>
                  <div style={{ fontSize: '12px', color: '#6b7280', background: '#f3f4f6', padding: '3px 8px', borderRadius: '4px' }}>
                    ID: {item.id}
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}

        {updatedItems.length > 0 && (
          <div style={{ marginBottom: '20px' }}>
            <h4 style={{ marginBottom: '12px', color: '#2563eb' }}>↻ Atualizados ({updatedItems.length}):</h4>
            <div style={{ maxHeight: '150px', overflowY: 'auto' }}>
              {updatedItems.map((item, idx) => (
                <div 
                  key={idx} 
                  style={{
                    padding: '8px 12px',
                    background: '#eff6ff',
                    border: '1px solid #bfdbfe',
                    borderRadius: '6px',
                    marginBottom: '6px'
                  }}
                >
                  <span style={{ fontWeight: '600' }}>{item.sku}</span>
                  <span style={{ fontSize: '12px', color: '#6b7280', marginLeft: '8px' }}>
                    {item.entity}
                  </span>
                </div>
              ))}
            </div>
          </div>
        )}

        {failedItems.length > 0 && (
          <div style={{ marginBottom: '20px' }}>
            <h4 style={{ marginBottom: '12px', color: '#dc2626' }}>✗ Falhas ({failedItems.length}):</h4>
            <div style={{ background: '#fef2f2', borderRadius: '6px', padding: '12px', maxHeight: '150px', overflowY: 'auto' }}>
              {failedItems.map((item, idx) => (
                <div key={idx} style={{ padding: '6px 0', color: '#dc2626', fontSize: '14px' }}>
                  • {item.sku} <span style={{ fontSize: '12px', color: '#991b1b' }}>({item.entity})</span>
                </div>
              ))}
            </div>
          </div>
        )}

        <div className="modal-actions">
          <button onClick={onClose} style={{ width: '100%' }}>
            Fechar
          </button>
        </div>
      </div>
    </div>
  );
}
