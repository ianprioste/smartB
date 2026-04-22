import React, { useEffect, useRef, useState } from 'react';
import { useNavigate, useLocation } from 'react-router-dom';
import { Layout } from '../../components/Layout';
import { summarizeDeletionMismatch, summarizePlannedDeletionRisk } from './planExecutionInsights';
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
  const [strictPlannedDeletions, setStrictPlannedDeletions] = useState(false);
  const [executionResultsModal, setExecutionResultsModal] = useState(null);
  const shortDescriptionRef = useRef(null);
  const shortDescriptionHtmlRef = useRef(null);
  const [showHtmlEditor, setShowHtmlEditor] = useState(false);

  function normalizeEditorHtml(input) {
    const value = String(input || '');
    if (!value) return '';
    // Decode escaped html (&lt;p&gt;...) when it arrives as text.
    if (value.includes('&lt;') && !value.includes('<')) {
      const textarea = document.createElement('textarea');
      textarea.innerHTML = value;
      return textarea.value;
    }
    return value;
  }

  async function fetchJsonWithTimeout(url, timeoutMs = 12000) {
    const controller = new AbortController();
    const timeoutId = setTimeout(() => controller.abort(), timeoutMs);
    const timeoutErrorPromise = new Promise((_, reject) => {
      setTimeout(() => {
        reject(new Error(`TIMEOUT:${url}`));
      }, timeoutMs + 50);
    });
    try {
      const response = await Promise.race([
        fetch(url, {
          credentials: 'include',
          signal: controller.signal,
        }),
        timeoutErrorPromise,
      ]);
      return response;
    } finally {
      clearTimeout(timeoutId);
    }
  }

  useEffect(() => {
    fetchConfiguration();
  }, []);

  useEffect(() => {
    if (step !== 3) return;
    if (!shortDescriptionRef.current || showHtmlEditor) return;
    if (document.activeElement === shortDescriptionRef.current) return;
    const nextHtml = normalizeEditorHtml(overrides.short_description || '');
    if (shortDescriptionRef.current.innerHTML !== nextHtml) {
      shortDescriptionRef.current.innerHTML = nextHtml;
    }
  }, [overrides.short_description, showHtmlEditor, step]);

  useEffect(() => {
    if (!editProduct?.id) return;
    fetchEditProductDetails(editProduct.id);
  }, [editProduct?.id]);

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
      const [modelsResult, colorsResult] = await Promise.allSettled([
        fetchJsonWithTimeout(`${API_BASE}/config/models`),
        fetchJsonWithTimeout(`${API_BASE}/config/colors`),
      ]);

      if (modelsResult.status !== 'fulfilled' || colorsResult.status !== 'fulfilled') {
        throw new Error('Tempo limite ao carregar configuração. Verifique backend e tente novamente.');
      }

      const modelsResp = modelsResult.value;
      const colorsResp = colorsResult.value;

      if (modelsResp.status === 401 || colorsResp.status === 401) {
        navigate('/login', { replace: true });
        return;
      }

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
      if (e.name === 'AbortError' || String(e.message || '').startsWith('TIMEOUT:')) {
        setError('Tempo limite ao carregar configuração. Tente novamente.');
      } else {
        setError(e.message || 'Erro ao carregar configuração');
      }
    } finally {
      setLoading(false);
    }
  }

  async function fetchEditProductDetails(productId) {
    try {
      const resp = await fetchJsonWithTimeout(`${API_BASE}/bling/products/${productId}`);
      if (resp.status === 401) {
        navigate('/login', { replace: true });
        return;
      }
      if (!resp.ok) return;

      const detail = await resp.json();
      const existingDescription = sanitizeImportedHtml(
        detail.descricao_curta || detail.descricaoCurta || detail.descricao || ''
      );

      if (existingDescription) {
        setOverrides((prev) => ({
          ...prev,
          short_description: existingDescription,
        }));
      }
    } catch {
      // Keep wizard usable even if detail fetch fails.
    }
  }

  function sanitizeImportedHtml(rawHtml) {
    const source = String(rawHtml || '');
    if (!source.trim()) return '';

    try {
      const parser = new DOMParser();
      const doc = parser.parseFromString(`<div>${source}</div>`, 'text/html');
      const root = doc.body.firstElementChild || doc.body;

      root.querySelectorAll('*').forEach((el) => {
        Array.from(el.attributes).forEach((attr) => {
          const name = (attr.name || '').toLowerCase();
          if (name.startsWith('data-')) {
            el.removeAttribute(attr.name);
          }
        });
      });

      root.querySelectorAll('p').forEach((p) => {
        const text = (p.textContent || '').replace(/\u00a0/g, '').trim();
        if (!text && p.children.length === 0) {
          p.remove();
        }
      });

      return root.innerHTML.trim();
    } catch {
      return source;
    }
  }

  function simplifyShortDescriptionHtml() {
    if (!shortDescriptionRef.current) return;
    const html = shortDescriptionRef.current.innerHTML;
    setOverrides((prev) => ({ ...prev, short_description: html || '' }));
  }

  function handleShortDescriptionInput() {
    simplifyShortDescriptionHtml();
  }

  function handleShortDescriptionPaste() {
    setTimeout(() => {
      simplifyShortDescriptionHtml();
    }, 0);
  }

  function applyShortDescriptionFormat(command) {
    if (!shortDescriptionRef.current) return;
    shortDescriptionRef.current.focus();
    try {
      document.execCommand(command, false, null);
    } catch (e) {}
    simplifyShortDescriptionHtml();
  }

  function toggleHtmlEditor() {
    if (!showHtmlEditor) {
      // Always read current visual content before switching to HTML mode.
      const liveHtml = shortDescriptionRef.current?.innerHTML || overrides.short_description || '';
      setOverrides((prev) => ({ ...prev, short_description: liveHtml }));
      if (shortDescriptionHtmlRef.current) {
        shortDescriptionHtmlRef.current.value = liveHtml;
      }
    } else {
      if (shortDescriptionHtmlRef.current) {
        const html = shortDescriptionHtmlRef.current.value || '';
        setOverrides((prev) => ({ ...prev, short_description: html }));
        // Apply immediately to visual editor to avoid stale rendering.
        if (shortDescriptionRef.current) {
          shortDescriptionRef.current.innerHTML = normalizeEditorHtml(html);
        }
      }
    }
    setShowHtmlEditor(!showHtmlEditor);
  }

  function handleHtmlChange(event) {
    setOverrides((prev) => ({ ...prev, short_description: event.target.value }));
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
        short_description: normalizeEditorHtml(overrides.short_description || '') || null,
        complement_description: null,
        complement_same_as_short: true,
        category_override_id: null,
        ncm: overrides.ncm || null,
        cest: overrides.cest || null,
      },
      options: {
        auto_seed_base_plain: false,
        stock_type: 'virtual',
        strict_planned_deletions: strictPlannedDeletions,
      },
      edit_parent_id: editProduct ? editProduct.id : null,
    };

    let resp;
    resp = await fetch(`${API_BASE}/plans/new-plain`, {
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
      setLoadingStatus('⚙️ Gerando preview do plano liso... isso pode levar alguns minutos.');
      setError(null);
      const planData = await generatePlanRequest();
      setPlan(planData);
      setLoadingStatus('✅ Preview gerado com sucesso!');
      setStep(4);
    } catch (e) {
      if (e.name === 'AbortError') {
        setError('A geração do plano foi cancelada antes de terminar. Tente novamente.');
      } else {
        setError(e.message || 'Erro ao gerar plano');
      }
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
      const executionPlan = {
        ...plan,
        options: {
          ...(plan.options || {}),
          strict_planned_deletions: strictPlannedDeletions,
        },
      };
      const response = await fetch('/api/plans/execute', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(executionPlan),
      });
      const data = await response.json();
      if (!response.ok) {
        throw new Error(data?.detail?.message || data?.detail || 'Falha na execução');
      }
      setExecutionResultsModal(data);
    } catch (e) {
      setError(e.message || 'Erro ao executar plano');
    } finally {
      setExecuting(false);
    }
  }

  const plannedDeletionRisk = summarizePlannedDeletionRisk(plan);

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
              <div className="description-header">
                <label>Descrição Curta (opcional)</label>
                <button
                  type="button"
                  className="html-toggle-btn"
                  onClick={toggleHtmlEditor}
                  title={showHtmlEditor ? 'Voltar para editor visual' : 'Editar HTML diretamente'}
                >
                  &lt;/&gt;
                </button>
              </div>

              {!showHtmlEditor ? (
                <div className="richtext-editor">
                  <div className="richtext-toolbar">
                    <button type="button" onClick={() => applyShortDescriptionFormat('undo')} title="Desfazer">↶</button>
                    <button type="button" onClick={() => applyShortDescriptionFormat('redo')} title="Refazer">↷</button>
                    <div className="richtext-divider"></div>
                    <button type="button" onClick={() => applyShortDescriptionFormat('bold')} title="Negrito">B</button>
                    <button type="button" onClick={() => applyShortDescriptionFormat('italic')} title="Itálico"><em>I</em></button>
                    <button type="button" onClick={() => applyShortDescriptionFormat('underline')} title="Sublinhado"><u>U</u></button>
                    <div className="richtext-divider"></div>
                    <button type="button" onClick={() => applyShortDescriptionFormat('insertUnorderedList')} title="Lista com Marcadores">• Lista</button>
                    <button type="button" onClick={() => applyShortDescriptionFormat('insertOrderedList')} title="Lista Numerada">1. Lista</button>
                    <button type="button" onClick={() => applyShortDescriptionFormat('justifyLeft')} title="Alinhar à Esquerda">⬅</button>
                    <button type="button" onClick={() => applyShortDescriptionFormat('justifyCenter')} title="Centralizar">⬍</button>
                    <button type="button" onClick={() => applyShortDescriptionFormat('justifyRight')} title="Alinhar à Direita">➡</button>
                    <button type="button" onClick={() => applyShortDescriptionFormat('justifyFull')} title="Justificar">⬌</button>
                  </div>
                  <div
                    ref={shortDescriptionRef}
                    className="richtext-input"
                    contentEditable
                    suppressContentEditableWarning
                    onInput={handleShortDescriptionInput}
                    onPaste={handleShortDescriptionPaste}
                  />
                </div>
              ) : (
                <textarea
                  ref={shortDescriptionHtmlRef}
                  className="html-editor"
                  value={overrides.short_description || ''}
                  onChange={handleHtmlChange}
                  placeholder="Digite o HTML aqui..."
                  spellCheck="false"
                />
              )}
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

            {plannedDeletionRisk.parentsWithPlannedDeletions > 0 && (
              <div className="blocker-warning" style={{ background: strictPlannedDeletions ? '#fff7ed' : '#fffbea', borderColor: strictPlannedDeletions ? '#fdba74' : '#facc15', color: '#78350f' }}>
                <strong>{strictPlannedDeletions ? '🔒 Modo estrito ativo.' : '⚠️ Atenção para exclusões planejadas.'}</strong>
                {' '}
                {plannedDeletionRisk.parentsWithPlannedDeletions} produto(s) pai têm remoções previstas, somando {plannedDeletionRisk.totalPlannedDeletionSkus} SKU(s).
              </div>
            )}

            <div className="noop-option-block">
              <div className="noop-checkbox">
                <input
                  type="checkbox"
                  id="strictPlannedDeletionsPlain"
                  checked={strictPlannedDeletions}
                  onChange={(e) => setStrictPlannedDeletions(e.target.checked)}
                />
                <label htmlFor="strictPlannedDeletionsPlain">
                  <strong>🔒 Modo estrito de exclusões planejadas</strong>
                  <br />
                  <small>Bloqueia UPDATE se as variações removidas divergirem do plano previsto.</small>
                </label>
              </div>
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
                      <td>{item.computed_payload_preview?.tributacao?.ncm || '-'}</td>
                      <td>{item.computed_payload_preview?.tributacao?.cest || '-'}</td>
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

        {executionResultsModal && (
          <PlainExecutionResultsModal
            results={executionResultsModal}
            onClose={() => setExecutionResultsModal(null)}
            onGoProducts={() => navigate('/products')}
          />
        )}
      </div>
    </Layout>
  );
}

function PlainExecutionResultsModal({ results, onClose, onGoProducts }) {
  if (!results) return null;

  const items = Array.isArray(results.results) ? results.results : [];
  const successItems = items.filter((item) => item.status === 'success');
  const createdItems = successItems.filter((item) => item.action === 'CREATE');
  const updatedItems = successItems.filter((item) => item.action === 'UPDATE');
  const noopItems = items.filter((item) => item.status === 'noop');
  const failedItems = items.filter((item) => item.status === 'failed');

  const createdFallback = createdItems.reduce(
    (acc, item) => acc + 1 + Number(item?.variations_count || 0),
    0,
  );
  const createdCount = Number(results?.summary?.created_items ?? createdFallback);
  const updatedCount = Number(results?.summary?.updated_items ?? updatedItems.length);
  const noopCount = Number(results?.summary?.noop_items ?? noopItems.length);

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal" onClick={(e) => e.stopPropagation()} style={{ maxWidth: '700px' }}>
        <h3>{failedItems.length > 0 ? '⚠️ Execução concluída com falhas' : '✅ Plano executado com sucesso'}</h3>

        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(5, 1fr)', gap: '10px', marginBottom: '20px' }}>
          <div style={{ background: '#f0fdf4', border: '1px solid #86efac', borderRadius: '8px', padding: '12px', textAlign: 'center' }}>
            <div style={{ fontSize: '20px', fontWeight: 'bold', color: '#16a34a' }}>{createdCount}</div>
            <div style={{ color: '#15803d', marginTop: '2px', fontSize: '11px' }}>🟢 Criados</div>
          </div>
          <div style={{ background: '#ecfeff', border: '1px solid #67e8f9', borderRadius: '8px', padding: '12px', textAlign: 'center' }}>
            <div style={{ fontSize: '20px', fontWeight: 'bold', color: '#0e7490' }}>{updatedCount}</div>
            <div style={{ color: '#155e75', marginTop: '2px', fontSize: '11px' }}>✅ Atualizados</div>
          </div>
          <div style={{ background: '#eff6ff', border: '1px solid #93c5fd', borderRadius: '8px', padding: '12px', textAlign: 'center' }}>
            <div style={{ fontSize: '20px', fontWeight: 'bold', color: '#2563eb' }}>{noopCount}</div>
            <div style={{ color: '#1e40af', marginTop: '2px', fontSize: '11px' }}>🔵 Sem mudança</div>
          </div>
          <div style={{ background: '#eff6ff', border: '1px solid #93c5fd', borderRadius: '8px', padding: '12px', textAlign: 'center' }}>
            <div style={{ fontSize: '20px', fontWeight: 'bold', color: '#2563eb' }}>{items.length}</div>
            <div style={{ color: '#1e40af', marginTop: '2px', fontSize: '11px' }}>Total processados</div>
          </div>
          <div style={{ background: failedItems.length > 0 ? '#fef2f2' : '#f9fafb', border: failedItems.length > 0 ? '1px solid #fca5a5' : '1px solid #e5e7eb', borderRadius: '8px', padding: '12px', textAlign: 'center' }}>
            <div style={{ fontSize: '20px', fontWeight: 'bold', color: failedItems.length > 0 ? '#dc2626' : '#6b7280' }}>{failedItems.length}</div>
            <div style={{ color: failedItems.length > 0 ? '#b91c1c' : '#6b7280', marginTop: '2px', fontSize: '11px' }}>❌ Falhas</div>
          </div>
        </div>

        {failedItems.length > 0 && (
          <div style={{ marginBottom: '20px' }}>
            <h4 style={{ marginBottom: '12px', color: '#dc2626' }}>Falhas</h4>
            <div style={{ background: '#fef2f2', borderRadius: '6px', padding: '12px', maxHeight: '320px', overflowY: 'auto' }}>
              {failedItems.map((item, idx) => {
                const errorText = item.error || item.error_message || item.message || item.detail;
                const mismatch = summarizeDeletionMismatch(item);
                const isStrictDeletionMismatch = errorText === 'Strict planned deletions mismatch';

                return (
                  <div key={idx} style={{ padding: '10px 0', fontSize: '14px', borderBottom: '1px solid #fecaca' }}>
                    <div style={{ color: '#dc2626' }}>• {item.sku} <span style={{ fontSize: '12px', color: '#991b1b' }}>({item.entity})</span></div>
                    {isStrictDeletionMismatch ? (
                      <div style={{ marginTop: '8px', marginLeft: '16px', background: '#fff7ed', border: '1px solid #fdba74', borderRadius: '6px', padding: '10px' }}>
                        <div style={{ fontWeight: 600, color: '#9a3412', marginBottom: '6px', fontSize: '13px' }}>🔒 Divergência entre exclusões planejadas e efetivas</div>
                        <div style={{ fontSize: '12px', color: '#7c2d12', marginBottom: '6px' }}><strong>Planejadas:</strong> {mismatch.planned.length > 0 ? mismatch.planned.join(', ') : 'nenhuma'}</div>
                        <div style={{ fontSize: '12px', color: '#991b1b', marginBottom: '6px' }}><strong>Remoções inesperadas:</strong> {mismatch.unexpected.length > 0 ? mismatch.unexpected.join(', ') : 'nenhuma'}</div>
                        <div style={{ fontSize: '12px', color: '#9a3412' }}><strong>Planejadas que não seriam removidas:</strong> {mismatch.missing.length > 0 ? mismatch.missing.join(', ') : 'nenhuma'}</div>
                      </div>
                    ) : (
                      <div style={{ marginTop: '4px', marginLeft: '16px', fontSize: '12px', color: '#991b1b', background: '#fee2e2', padding: '6px', borderRadius: '4px' }}>
                        {errorText || 'Falha na execução'}
                      </div>
                    )}
                  </div>
                );
              })}
            </div>
          </div>
        )}

        <div className="modal-actions">
          <button onClick={onClose}>Fechar</button>
          <button onClick={onGoProducts}>Ir para Produtos</button>
        </div>
      </div>
    </div>
  );
}
