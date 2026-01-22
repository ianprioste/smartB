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

      setModels(modelsData.filter(m => m.is_active));
      setColors(colorsData.filter(c => c.is_active));
    } catch (err) {
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
      };

      setLoadingStatus('⚙️ Gerando plano no servidor...');

      const resp = await fetch(`${API_BASE}/plans/new`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      });

      if (!resp.ok) {
        const errorData = await resp.json();
        throw new Error(errorData.detail?.message || 'Falha ao gerar plano');
      }

      setLoadingStatus('📦 Processando itens do plano...');
      const planData = await resp.json();
      
      await new Promise(resolve => setTimeout(resolve, 300));
      setLoadingStatus('✅ Plano gerado com sucesso!');
      
      await new Promise(resolve => setTimeout(resolve, 500));
      setPlan(planData);
      setStep(4); // Go to preview
    } catch (err) {
      setError(err.message);
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
          onExecute={() => alert('Execução será implementada na próxima sprint!')}
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
    </div>
  );
}

function PlanPreview({ plan, onBack, onExecute }) {
  const hasBlockers = plan.has_blockers;

  // Group items by action
  const itemsByAction = {
    CREATE: plan.items.filter(i => i.action === 'CREATE'),
    UPDATE: plan.items.filter(i => i.action === 'UPDATE'),
    NOOP: plan.items.filter(i => i.action === 'NOOP'),
    BLOCKED: plan.items.filter(i => i.action === 'BLOCKED'),
  };

  return (
    <div className="wizard-content preview-content">
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

      {hasBlockers && (
        <div className="blocker-warning">
          ⚠️ <strong>Existem bloqueios!</strong> Corrija Templates antes de continuar.
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
                    {item.reason && <div className="reason-tag">{item.reason}</div>}
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
        <button className="btn-primary" onClick={onExecute} disabled={hasBlockers}>
          {hasBlockers ? '🚫 Bloqueado' : '✅ Executar (próxima sprint)'}
        </button>
      </div>
    </div>
  );
}
