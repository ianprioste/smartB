import React, { useEffect, useState } from 'react';
import { useNavigate, useLocation } from 'react-router-dom';
import { Layout } from '../../components/Layout';
import '../../styles/wizard.css';

const API_BASE = '/api';

export function WizardPlainPage() {
  const navigate = useNavigate();
  const location = useLocation();
  const editProduct = location.state?.editProduct || null;
  const [step, setStep] = useState(1);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  const [models, setModels] = useState([]);
  const [colors, setColors] = useState([]);

  const [parentSku, setParentSku] = useState((editProduct?.codigo || '').toUpperCase());
  const [parentName, setParentName] = useState(editProduct?.nome || '');
  const [selectedModel, setSelectedModel] = useState('');
  const [selectedSizes, setSelectedSizes] = useState([]);
  const [selectedColors, setSelectedColors] = useState([]);
  const [price, setPrice] = useState('');

  const [overrides, setOverrides] = useState({
    short_description: '',
    ncm: '6109.10.00',
    cest: '28.059.00',
  });

  const [plan, setPlan] = useState(null);
  const [generatingPlan, setGeneratingPlan] = useState(false);
  const [loadingStatus, setLoadingStatus] = useState('');
  const [executing, setExecuting] = useState(false);

  useEffect(() => {
    fetchConfiguration();
  }, []);

  useEffect(() => {
    if (!editProduct?.id) return;
    // Try to infer model by SKU prefix for a smoother edit experience.
    const skuUpper = String(editProduct.codigo || '').toUpperCase();
    const byPrefix = [...models]
      .sort((a, b) => String(b.code || '').length - String(a.code || '').length)
      .find((m) => skuUpper.startsWith(String(m.code || '').toUpperCase()));

    if (byPrefix) {
      setSelectedModel(byPrefix.code);
      setSelectedSizes(byPrefix.allowed_sizes ? [...byPrefix.allowed_sizes] : []);
    }
  }, [editProduct?.id, editProduct?.codigo, models]);

  async function fetchConfiguration() {
    try {
      setLoading(true);
      setError(null);
      const [modelsResp, colorsResp] = await Promise.all([
        fetch(`${API_BASE}/config/models`),
        fetch(`${API_BASE}/config/colors`),
      ]);

      if (!modelsResp.ok || !colorsResp.ok) {
        throw new Error('Falha ao carregar configuração');
      }

      const modelsData = await modelsResp.json();
      const colorsData = await colorsResp.json();

      const activeModels = modelsData.filter((m) => m.is_active);
      const activeColors = colorsData.filter((c) => c.is_active);

      setModels(activeModels);
      setColors(activeColors);
    } catch (e) {
      setError(e.message || 'Erro ao carregar configuração');
    } finally {
      setLoading(false);
    }
  }

  function handleSelectModel(code) {
    if (selectedModel === code) {
      // Same UX as printed wizard: click again to unselect.
      setSelectedModel('');
      setSelectedSizes([]);
      setPrice('');
      return;
    }

    setSelectedModel(code);
    const model = models.find((m) => m.code === code);
    if (model?.allowed_sizes?.length) {
      setSelectedSizes([...model.allowed_sizes]);
    } else {
      setSelectedSizes([]);
    }
  }

  function handleSizeToggle(size) {
    setSelectedSizes((prev) => (prev.includes(size) ? prev.filter((s) => s !== size) : [...prev, size]));
  }

  function handleColorToggle(code) {
    setSelectedColors((prev) => (prev.includes(code) ? prev.filter((c) => c !== code) : [...prev, code]));
  }

  async function generatePlanRequest() {
    const payload = {
      parent_sku: parentSku.trim().toUpperCase(),
      parent_name: parentName.trim(),
      model_code: selectedModel,
      sizes: selectedSizes,
      colors: selectedColors,
      price: parseFloat(price),
      overrides: {
        short_description: overrides.short_description || null,
        complement_description: null,
        complement_same_as_short: true,
        category_override_id: null,
        ncm: overrides.ncm || null,
        cest: overrides.cest || null,
      },
      options: {
        auto_seed_base_plain: false,
        stock_type: 'virtual',
      },
      edit_parent_id: editProduct ? editProduct.id : null,
    };

    const resp = await fetch(`${API_BASE}/plans/new-plain`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    });

    if (!resp.ok) {
      const errorData = await resp.json().catch(() => ({}));
      const message = errorData?.detail?.message || errorData?.message || 'Falha ao gerar plano liso';
      throw new Error(message);
    }

    return await resp.json();
  }

  async function handleGeneratePlan() {
    if (!parentSku.trim() || !parentName.trim()) {
      setError('Informe SKU e título do produto pai');
      return;
    }
    if (!selectedModel) {
      setError('Selecione um modelo');
      return;
    }
    if (selectedSizes.length === 0) {
      setError('Selecione pelo menos um tamanho');
      return;
    }
    if (selectedColors.length === 0) {
      setError('Selecione pelo menos uma cor');
      return;
    }
    const parsedPrice = parseFloat(price);
    if (!parsedPrice || parsedPrice <= 0) {
      setError('Informe um preço válido');
      return;
    }

    try {
      setGeneratingPlan(true);
      setLoadingStatus('⚙️ Gerando preview do plano liso...');
      setError(null);
      const planData = await generatePlanRequest();
      setPlan(planData);
      setLoadingStatus('✅ Preview gerado com sucesso!');
      setStep(4);
    } catch (e) {
      setError(e.message || 'Erro ao gerar plano');
    } finally {
      setGeneratingPlan(false);
      setLoadingStatus('');
    }
  }

  async function handleExecutePlan() {
    if (!plan) return;
    try {
      setExecuting(true);
      setError(null);
      const response = await fetch('/api/plans/execute', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(plan),
      });
      const data = await response.json();
      if (!response.ok) {
        throw new Error(data?.detail?.message || data?.detail || 'Falha na execução');
      }
      alert(`Execução concluída. Sucesso: ${data?.summary?.success || 0}, Falhas: ${data?.summary?.failed || 0}`);
      navigate('/products');
    } catch (e) {
      setError(e.message || 'Erro ao executar plano');
    } finally {
      setExecuting(false);
    }
  }

  return (
    <Layout>
      <div className="wizard-container">
        {(generatingPlan || executing) && (
          <div className="loading-modal-overlay">
            <div className="loading-modal">
              <div className="loading-spinner"></div>
              <h2>{loadingStatus || (executing ? 'Executando plano no Bling...' : 'Processando...')}</h2>
              <p>Por favor, aguarde...</p>
            </div>
          </div>
        )}

        <header className="wizard-header">
          <h1>{editProduct ? '🧩 Wizard: Assistente de Atualização' : '🧩 Wizard: Novo Produto Liso'}</h1>
          <button className="btn-secondary" onClick={() => navigate('/products')}>← Voltar</button>
        </header>

        <div className="wizard-progress">
          <div className={`wizard-step ${step >= 1 ? 'active' : ''} ${step > 1 ? 'completed' : ''}`}>1. Pai</div>
          <div className={`wizard-step ${step >= 2 ? 'active' : ''} ${step > 2 ? 'completed' : ''}`}>2. Modelo/Tamanhos</div>
          <div className={`wizard-step ${step >= 3 ? 'active' : ''} ${step > 3 ? 'completed' : ''}`}>3. Cores</div>
          <div className={`wizard-step ${step >= 4 ? 'active' : ''}`}>4. Preview</div>
        </div>

        {error && <div className="wizard-error">❌ {error}</div>}
        {loading && <div className="wizard-loading">Carregando configuração...</div>}

        {!loading && step === 1 && (
          <div className="wizard-content">
            <h2>🧾 Dados do Produto Pai</h2>
            <div className="form-group">
              <label>SKU do Pai *</label>
              <input value={parentSku} onChange={(e) => setParentSku(e.target.value.toUpperCase())} placeholder="Ex.: CAMBAS" />
              <small>Os filhos serão gerados como: SKU_PAI + COR + TAMANHO</small>
            </div>
            <div className="form-group">
              <label>Título do Pai *</label>
              <input value={parentName} onChange={(e) => setParentName(e.target.value)} placeholder="Ex.: Camiseta Básica" />
            </div>
            <div className="form-group">
              <label>Preço (R$) *</label>
              <input
                type="number"
                step="0.01"
                min="0"
                value={price}
                onChange={(e) => setPrice(e.target.value)}
                placeholder="Ex: 79.90"
              />
            </div>
            <div className="wizard-actions">
              <button className="btn-primary" onClick={() => setStep(2)}>Próximo →</button>
            </div>
          </div>
        )}

        {!loading && step === 2 && (
          <div className="wizard-content">
            <h2>📐 Selecione os Modelos e Tamanhos</h2>
            <div className="models-grid">
              {models.map((m) => {
                const selected = selectedModel === m.code;
                return (
                  <div key={m.code} className={`model-card ${selected ? 'selected' : ''}`}>
                    <div className="model-header" onClick={() => handleSelectModel(m.code)}>
                      <input type="checkbox" checked={selected} readOnly />
                      <strong>{m.code}</strong> - {m.name}
                    </div>
                    {selected && (
                      <div className="sizes-selection">
                        <label>Tamanhos:</label>
                        <div className="sizes-buttons">
                          {m.allowed_sizes.map((size) => (
                            <button
                              key={size}
                              type="button"
                              className={`size-btn ${selectedSizes.includes(size) ? 'active' : ''}`}
                              onClick={() => handleSizeToggle(size)}
                            >
                              {size}
                            </button>
                          ))}
                        </div>
                      </div>
                    )}
                  </div>
                );
              })}
            </div>

            <div className="wizard-actions">
              <button className="btn-secondary" onClick={() => setStep(1)}>← Voltar</button>
              <button className="btn-primary" onClick={() => setStep(3)}>Próximo →</button>
            </div>
          </div>
        )}

        {!loading && step === 3 && (
          <div className="wizard-content">
            <h2>🎨 Selecione as Cores</h2>
            <div className="colors-grid">
              {colors.map((c) => (
                <div
                  key={c.code}
                  className={`color-card ${selectedColors.includes(c.code) ? 'selected' : ''}`}
                  onClick={() => handleColorToggle(c.code)}
                >
                  <input type="checkbox" checked={selectedColors.includes(c.code)} readOnly />
                  <strong>{c.code}</strong> - {c.name}
                </div>
              ))}
            </div>

            <div className="form-group" style={{ marginTop: 16 }}>
              <label>Descrição Curta (opcional)</label>
              <textarea
                value={overrides.short_description}
                onChange={(e) => setOverrides((prev) => ({ ...prev, short_description: e.target.value }))}
                rows={3}
              />
            </div>

            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12 }}>
              <div className="form-group">
                <label>NCM</label>
                <input value={overrides.ncm} onChange={(e) => setOverrides((prev) => ({ ...prev, ncm: e.target.value }))} />
              </div>
              <div className="form-group">
                <label>CEST</label>
                <input value={overrides.cest} onChange={(e) => setOverrides((prev) => ({ ...prev, cest: e.target.value }))} />
              </div>
            </div>

            <div className="wizard-actions">
              <button className="btn-secondary" onClick={() => setStep(2)}>← Voltar</button>
              <button className="btn-primary" onClick={handleGeneratePlan} disabled={generatingPlan}>
                {generatingPlan ? 'Gerando...' : 'Gerar Preview'}
              </button>
            </div>
          </div>
        )}

        {!loading && step === 4 && plan && (
          <div className="wizard-content preview-content">
            <h2>📊 Preview do Plano (Produto Liso)</h2>

            <div className="plan-summary">
              <div className="summary-card"><strong>{plan.summary.total_skus}</strong><span>Total SKUs</span></div>
              <div className="summary-card status-create"><strong>{plan.summary.create_count}</strong><span>🟢 Criar</span></div>
              <div className="summary-card status-update"><strong>{plan.summary.update_count}</strong><span>🟡 Atualizar</span></div>
              <div className="summary-card status-noop"><strong>{plan.summary.noop_count}</strong><span>🔵 Sem mudança</span></div>
              <div className="summary-card status-blocked"><strong>{plan.summary.blocked_count}</strong><span>🔴 Bloqueado</span></div>
            </div>

            <div className="plan-table-container">
              <table className="plan-table">
                <thead>
                  <tr>
                    <th>SKU</th>
                    <th>Tipo</th>
                    <th>Ação</th>
                    <th>Preço</th>
                    <th>NCM</th>
                    <th>CEST</th>
                    <th>Dependências</th>
                    <th>Template</th>
                    <th>Motivo</th>
                  </tr>
                </thead>
                <tbody>
                  {plan.items.map((item, idx) => (
                    <tr key={idx} className={`status-${item.action.toLowerCase()}`}>
                      <td><code>{item.sku}</code></td>
                      <td>{item.entity === 'BASE_PARENT' ? 'Base Pai' : 'Base Variação'}</td>
                      <td>
                        <span className={`badge badge-${item.action.toLowerCase()}`}>
                          {item.action === 'CREATE' && 'Criar'}
                          {item.action === 'UPDATE' && 'Atualizar'}
                          {item.action === 'NOOP' && 'OK'}
                          {item.action === 'BLOCKED' && 'Bloqueado'}
                        </span>
                      </td>
                      <td>{item.computed_payload_preview?.preco ?? '-'}</td>
                      <td>{item.computed_payload_preview?.ncm || '-'}</td>
                      <td>{item.computed_payload_preview?.cest || '-'}</td>
                      <td>{(item.hard_dependencies || []).join(', ') || '-'}</td>
                      <td>{item.template ? `${item.template.model} / ${item.template.kind}` : '-'}</td>
                      <td>{item.reason || item.message || '-'}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>

            <div className="wizard-actions">
              <button className="btn-secondary" onClick={() => setStep(3)}>← Voltar</button>
              <button className="btn-primary" onClick={handleExecutePlan} disabled={executing || plan.has_blockers}>
                {executing ? 'Executando...' : (plan.has_blockers ? '🚫 Bloqueado' : '✅ Executar no Bling')}
              </button>
            </div>
          </div>
        )}
      </div>
    </Layout>
  );
}
