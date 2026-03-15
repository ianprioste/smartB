import React, { useState, useEffect, useRef } from 'react';
import { useNavigate, useLocation } from 'react-router-dom';
import { Layout } from '../../components/Layout';
import '../../styles/wizard.css';

const API_BASE = 'http://localhost:8000';
const PRODUCTS_CACHE_KEY = 'smartb_products_catalog_v1';
const PRODUCTS_CACHE_SAVED_AT_KEY = 'smartb_products_catalog_saved_at_v1';

export function WizardNewPage() {
  const navigate = useNavigate();
  const location = useLocation();
  const editProduct = location.state?.editProduct || null;

  // Derive print code: first segment of SKU before '-', e.g. "STPV-CAM" → "STPV"
  const initialPrintCode = editProduct
    ? (editProduct.codigo || '').split('-')[0].toUpperCase()
    : '';
  const initialPrintName = editProduct ? (editProduct.nome || '') : '';

  const [step, setStep] = useState(1);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  // Configuration data
  const [models, setModels] = useState([]);
  const [colors, setColors] = useState([]);

  // Form data
  const [printInfo, setPrintInfo] = useState({ code: initialPrintCode, name: initialPrintName });
  const [selectedModels, setSelectedModels] = useState([]); // [{code, name, allowed_sizes, selected_sizes}]
  const [selectedColors, setSelectedColors] = useState([]);
  const [overrides, setOverrides] = useState({
    short_description: '',
    complement_description: '',
    complement_same_as_short: true,
    ncm: '6109.10.00',
    cest: '28.059.00',
  });

  const [stockType, setStockType] = useState('virtual');
  const shortDescriptionRef = useRef(null);
  const shortDescriptionHtmlRef = useRef(null);
  const [showHtmlEditor, setShowHtmlEditor] = useState(false);

  // Plan data
  const [plan, setPlan] = useState(null);
  const [generatingPlan, setGeneratingPlan] = useState(false);
  const [loadingStatus, setLoadingStatus] = useState('');
  const [showReauthModal, setShowReauthModal] = useState(false);
  const [pendingRetryAfterReauth, setPendingRetryAfterReauth] = useState(false);
  const [seedResultsModal, setSeedResultsModal] = useState(null);
  const [executionResultsModal, setExecutionResultsModal] = useState(null);
  const [lastExecutedPlan, setLastExecutedPlan] = useState(null);

  useEffect(() => {
    fetchConfiguration();
  }, []);

  useEffect(() => {
    if (!editProduct?.id) return;
    fetchEditProductDetails(editProduct.id);
  }, [editProduct?.id]);

  function extractApiErrorMessage(errorData, fallbackMessage) {
    if (!errorData) return fallbackMessage;
    if (typeof errorData === 'string') return errorData;
    if (typeof errorData.detail === 'string') return errorData.detail;
    if (typeof errorData.detail?.message === 'string') return errorData.detail.message;
    if (typeof errorData.message === 'string') return errorData.message;
    if (typeof errorData.error === 'string') return errorData.error;
    return fallbackMessage;
  }

  function extractAffectedSkusFromExecutionResult(executionResult) {
    const skus = new Set();
    const resultItems = executionResult?.results || [];

    resultItems.forEach((item) => {
      if (item?.sku) skus.add(String(item.sku).toUpperCase());
      if (Array.isArray(item?.removed_variations)) {
        item.removed_variations.forEach((sku) => {
          if (sku) skus.add(String(sku).toUpperCase());
        });
      }
    });

    return Array.from(skus);
  }

  function readProductsCacheSafe() {
    try {
      const raw = localStorage.getItem(PRODUCTS_CACHE_KEY);
      const parsed = raw ? JSON.parse(raw) : [];
      return Array.isArray(parsed) ? parsed : [];
    } catch (e) {
      return [];
    }
  }

  async function fetchCatalogPage(page, limit, includeHierarchy, q = '') {
    const params = new URLSearchParams({
      page: String(page),
      limit: String(limit),
      include_hierarchy: includeHierarchy ? 'true' : 'false',
    });
    if (q) params.set('q', q);

    const resp = await fetch(`${API_BASE}/bling/products/list/all?${params}`);
    if (!resp.ok) throw new Error('Falha ao sincronizar cache local de produtos');
    return await resp.json();
  }

  async function refreshProductsCacheIncremental(targetSkus) {
    const normalizedSkus = Array.from(
      new Set((targetSkus || []).map((s) => String(s || '').trim().toUpperCase()).filter(Boolean))
    );
    if (normalizedSkus.length === 0) return 0;

    const currentCatalog = readProductsCacheSafe();
    const byId = new Map(currentCatalog.map((item) => [item.id, item]));

    // Process sequentially to avoid triggering Bling rate limits on burst updates.
    for (const sku of normalizedSkus) {
      try {
        const data = await fetchCatalogPage(1, 100, false, sku);
        const foundItems = (data?.items || []).filter(
          (item) => String(item?.codigo || '').trim().toUpperCase() === sku
        );

        if (foundItems.length > 0) {
          foundItems.forEach((item) => {
            if (item?.id != null) byId.set(item.id, item);
          });
        } else {
          // SKU no longer exists in Bling: remove stale cache entry.
          const idsToDelete = [];
          byId.forEach((item, id) => {
            if (String(item?.codigo || '').trim().toUpperCase() === sku) {
              idsToDelete.push(id);
            }
          });
          idsToDelete.forEach((id) => byId.delete(id));
        }
      } catch (err) {
        console.warn(`Falha no refresh incremental do SKU ${sku}:`, err);
      }
    }

    const catalog = Array.from(byId.values());
    localStorage.setItem(PRODUCTS_CACHE_KEY, JSON.stringify(catalog));
    localStorage.setItem(PRODUCTS_CACHE_SAVED_AT_KEY, new Date().toISOString());
    return catalog.length;
  }

  async function refreshProductsCacheFromBling(options = {}) {
    const targetSkus = options?.skus || [];
    const existingCatalog = readProductsCacheSafe();

    if (targetSkus.length > 0 && existingCatalog.length > 0) {
      return await refreshProductsCacheIncremental(targetSkus);
    }

    const pageSize = 100;
    const firstData = await fetchCatalogPage(1, pageSize, false);
    const firstItems = firstData.items || [];
    const totalCatalogPages = Math.ceil((firstData.total || 0) / pageSize);

    const restItems = [];
    for (let pageNum = 2; pageNum <= totalCatalogPages; pageNum += 1) {
      let data = null;
      try {
        data = await fetchCatalogPage(pageNum, pageSize, false);
      } catch (e) {
        continue;
      }
      restItems.push(...(data.items || []));
    }

    const dedupedById = new Map();
    [...firstItems, ...restItems].forEach((item) => dedupedById.set(item.id, item));
    const catalog = Array.from(dedupedById.values());

    localStorage.setItem(PRODUCTS_CACHE_KEY, JSON.stringify(catalog));
    localStorage.setItem(PRODUCTS_CACHE_SAVED_AT_KEY, new Date().toISOString());
    return catalog.length;
  }

  useEffect(() => {
    if (!shortDescriptionRef.current || showHtmlEditor) return;
    if (document.activeElement === shortDescriptionRef.current) return;
    const nextHtml = overrides.short_description || '';
    if (shortDescriptionRef.current.innerHTML !== nextHtml) {
      shortDescriptionRef.current.innerHTML = nextHtml;
    }
  }, [overrides.short_description, showHtmlEditor]);

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

      const activeModels = modelsData.filter(m => m.is_active);
      const activeColors = colorsData.filter(c => c.is_active);

      setModels(activeModels);
      setColors(activeColors);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }

  async function fetchEditProductDetails(productId) {
    try {
      const resp = await fetch(`${API_BASE}/bling/products/${productId}`);
      if (!resp.ok) return;

      const detail = await resp.json();
      const existingDescription =
        detail.descricao_curta || detail.descricaoCurta || detail.descricao || '';

      if (existingDescription) {
        setOverrides(prev => ({
          ...prev,
          short_description: existingDescription,
        }));
      }
    } catch (err) {
      // Keep wizard usable even if detail fetch fails.
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

  function simplifyShortDescriptionHtml() {
    if (!shortDescriptionRef.current) return;
    const html = shortDescriptionRef.current.innerHTML;
    setOverrides(prev => ({ ...prev, short_description: html || '' }));
  }

  function handleShortDescriptionInput() {
    simplifyShortDescriptionHtml();
  }

  function handleShortDescriptionKeyDown(event) {
    // Allow all keys including Enter for multi-line input
  }

  function handleShortDescriptionPaste(event) {
    // Allow paste with formatting
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
      // Switch to HTML mode - sync from visual to HTML textarea
      if (shortDescriptionHtmlRef.current) {
        shortDescriptionHtmlRef.current.value = overrides.short_description || '';
      }
    } else {
      // Switch back to visual mode - sync from HTML textarea to visual
      if (shortDescriptionHtmlRef.current) {
        const html = shortDescriptionHtmlRef.current.value || '';
        setOverrides(prev => ({ ...prev, short_description: html }));
      }
    }
    setShowHtmlEditor(!showHtmlEditor);
  }

  function handleHtmlChange(event) {
    setOverrides(prev => ({ ...prev, short_description: event.target.value }));
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
        complement_description: null,
        complement_same_as_short: true,
        category_override_id: null,
        ncm: overrides.ncm || null,
        cest: overrides.cest || null,
      },
      options: {
        auto_seed_base_plain: autoSeedBasePlain,
        stock_type: stockType,
      },
      edit_parent_id: editProduct ? editProduct.id : null,
    };

    const resp = await fetch(`${API_BASE}/plans/new`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    });

    if (!resp.ok) {
      const errorData = await resp.json().catch(() => ({}));
      
      // Check for token expiration
      if (resp.status === 401 && errorData.detail?.code === 'BLING_TOKEN_EXPIRED') {
        const error = new Error('Token expirado');
        error.code = 'BLING_TOKEN_EXPIRED';
        error.status = 401;
        throw error;
      }
      
      throw new Error(extractApiErrorMessage(errorData, 'Falha ao gerar plano'));
    }

    const planData = await resp.json();
    return planData;
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
    <Layout>
    <div className="wizard-container">
      <header className="wizard-header">
        <h1>{editProduct ? '✏️ Assistente de Atualização' : '🪄 Assistente de Novo Cadastro'}</h1>
        <button className="btn-secondary" onClick={() => navigate(editProduct ? '/products' : '/admin/models')}>
          ← Voltar
        </button>
      </header>

      {editProduct && (
        <div style={{
          background: '#eff6ff', border: '1px solid #93c5fd', borderRadius: 8,
          padding: '12px 18px', marginBottom: 16, fontSize: 13, color: '#1e40af',
        }}>
          ✏️ <strong>Editando produto:</strong> {editProduct.nome}
          {' '}<code style={{ background: '#dbeafe', padding: '2px 6px', borderRadius: 4 }}>{editProduct.codigo}</code>
          {' '}— O código da estampa foi extraído automaticamente do SKU. Ajuste se necessário antes de continuar.
        </div>
      )}

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
            <div className="form-group form-group-full">
              <div className="description-header">
                <label>Descrição</label>
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
                    <button type="button" onClick={() => applyShortDescriptionFormat('indent')} title="Aumentar Recuo">&gt;&gt;</button>
                    <button type="button" onClick={() => applyShortDescriptionFormat('outdent')} title="Diminuir Recuo">&lt;&lt;</button>
                    <div className="richtext-divider"></div>
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
                    onKeyDown={handleShortDescriptionKeyDown}
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
              <small>A descrição complementar e a categoria sempre usarão o template padrão</small>
            </div>
            <div className="ncm-cest-row">
              <div className="form-group">
                <label>NCM (opcional)</label>
                <input
                  type="text"
                  value={overrides.ncm}
                  onChange={e => setOverrides({ ...overrides, ncm: e.target.value })}
                  placeholder="Ex: 61091000"
                  maxLength={16}
                />
                <small>Aplicado em produtos e subprodutos criados/atualizados</small>
              </div>
              <div className="form-group">
                <label>CEST (opcional)</label>
                <input
                  type="text"
                  value={overrides.cest}
                  onChange={e => setOverrides({ ...overrides, cest: e.target.value })}
                  placeholder="Ex: 28.038.00"
                  maxLength={16}
                />
                <small>Aplicado em produtos e subprodutos criados/atualizados</small>
              </div>
            </div>
          </div>

          <div className="stock-type-group">
            <h3 className="stock-type-title">Tipo de Estoque</h3>
            <div className="stock-type-grid">
              <label className={`stock-type-card ${stockType === 'virtual' ? 'selected' : ''}`}>
                <input
                  type="radio"
                  name="stockType"
                  value="virtual"
                  checked={stockType === 'virtual'}
                  onChange={() => setStockType('virtual')}
                />
                <div className="stock-type-content">
                  <div className="stock-type-header">
                    <strong>Estoque Virtual</strong>
                  </div>
                  <small>Composicao com base lisa (formato E)</small>
                </div>
              </label>

              <label className={`stock-type-card ${stockType === 'physical' ? 'selected' : ''}`}>
                <input
                  type="radio"
                  name="stockType"
                  value="physical"
                  checked={stockType === 'physical'}
                  onChange={() => setStockType('physical')}
                />
                <div className="stock-type-content">
                  <div className="stock-type-header">
                    <strong>Estoque Fisico</strong>
                  </div>
                  <small>Variacao simples herdando dados do pai (formato S)</small>
                </div>
              </label>
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
                const errorData = await response.json().catch(() => ({}));
                throw new Error(extractApiErrorMessage(errorData, 'Erro ao executar plano'));
              }
              
              const result = await response.json();
              const affectedSkus = extractAffectedSkusFromExecutionResult(result);

              // Keep product base aligned with Bling after execute (creates/updates).
              setLoadingStatus('Sincronizando base local de produtos...');
              try {
                await refreshProductsCacheFromBling({ skus: affectedSkus });
              } catch (syncErr) {
                // Do not block success flow if cache sync fails.
                console.warn('Falha ao sincronizar cache local de produtos:', syncErr);
              }

              setLastExecutedPlan(currentPlan);
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
          executedPlan={lastExecutedPlan}
          onRecreateFailedUpdates={async (failedUpdateSkus) => {
            if (!lastExecutedPlan || !failedUpdateSkus?.length) return null;

            const confirmed = window.confirm(
              `Nao foi possivel atualizar ${failedUpdateSkus.length} produto(s). Deseja apagar esses produtos e cria-los novamente?`
            );
            if (!confirmed) return null;

            setGeneratingPlan(true);
            setLoadingStatus('Apagando e recriando produtos com falha de atualizacao...');

            try {
              const resp = await fetch('/api/plans/recreate-failed-updates', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                  plan: lastExecutedPlan,
                  failed_update_skus: failedUpdateSkus,
                }),
              });

              const data = await resp.json().catch(() => ({}));
              if (!resp.ok) {
                throw new Error(data?.detail?.message || data?.detail || data?.message || 'Falha ao recriar produtos');
              }

              const recreated = data?.summary?.recreated || 0;
              const failed = data?.summary?.failed || 0;
              const inPlaceRecovered = (data?.results || []).filter(
                (r) => r?.status === 'recreated' && r?.recovery_mode === 'in_place_update'
              ).length;
              const affectedSkus = extractAffectedSkusFromExecutionResult(data);

              // Re-sync local product cache after delete/recreate flow.
              try {
                await refreshProductsCacheFromBling({ skus: affectedSkus });
              } catch (syncErr) {
                console.warn('Falha ao sincronizar cache local de produtos:', syncErr);
              }

              if (inPlaceRecovered > 0) {
                alert(
                  `Recriacao concluida: ${recreated} recuperado(s), ${failed} falha(s). ` +
                  `${inPlaceRecovered} item(ns) foram recuperados no mesmo ID porque o Bling bloqueou a exclusao.`
                );
              } else {
                alert(`Recriacao concluida: ${recreated} recriado(s), ${failed} falha(s).`);
              }
              return data;
            } finally {
              setGeneratingPlan(false);
              setLoadingStatus('');
            }
          }}
          onClose={() => setExecutionResultsModal(null)} 
        />
      )}
    </div>
    </Layout>
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
              <th>NCM</th>
              <th>CEST</th>
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
                <td>{item.computed_payload_preview?.ncm || '-'}</td>
                <td>{item.computed_payload_preview?.cest || '-'}</td>
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
              <div key={idx} style={{ padding: '8px', color: '#dc2626', marginBottom: '8px' }}>
                <div style={{ fontWeight: '600' }}>• {item.sku}</div>
                {item.error && (
                  <div style={{ fontSize: '12px', color: '#991b1b', marginTop: '4px', marginLeft: '16px', background: '#fee2e2', padding: '6px', borderRadius: '4px' }}>
                    {item.error}
                  </div>
                )}
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

function ExecutionResultsModal({ results, executedPlan, onRecreateFailedUpdates, onClose }) {
  if (!results) return null;

  const { summary, results: items } = results;
  const successItems = items.filter(r => r.status === 'success');
  const failedItems = items.filter(r => r.status === 'failed');
  
  const createdItems = successItems.filter(r => r.action === 'CREATE');
  const updatedItems = successItems.filter(r => r.action === 'UPDATE');
  const failedUpdateItems = failedItems.filter(r => r.action === 'UPDATE');

  // Derive accurate counters from executed items when backend summary is absent/incomplete.
  const createdParentsCount = summary?.created_parents ??
    successItems.filter(r => r.action === 'CREATE' && r.entity === 'PARENT_PRINTED').length;
  const createdBasesCount = summary?.created_bases ??
    successItems.filter(r => r.action === 'CREATE' && r.entity === 'BASE_PARENT').length;
  const createdVariationsCount = summary?.created_variations ??
    createdItems.reduce((acc, item) => acc + Number(item.variations_count || 0), 0);

  const updatedParentsCount = summary?.updated_parents ??
    successItems.filter(r => r.action === 'UPDATE' && r.entity === 'PARENT_PRINTED').length;
  const updatedVariationsCount = summary?.updated_variations ??
    updatedItems.reduce((acc, item) => acc + Number(item.variations_count || 0), 0);
  const removedVariationsCount =
    summary?.removed_variations ??
    updatedItems.reduce((acc, item) => acc + Number(item.removed_variations_count || 0), 0);
  const updatedDisplayCount = (updatedVariationsCount > 0)
    ? updatedVariationsCount
    : updatedParentsCount;

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal" onClick={(e) => e.stopPropagation()} style={{ maxWidth: '700px' }}>
        <h3>✅ Plano Executado com Sucesso</h3>
        
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(6, 1fr)', gap: '10px', marginBottom: '20px' }}>
          <div style={{ background: '#f0fdf4', border: '1px solid #86efac', borderRadius: '8px', padding: '12px', textAlign: 'center' }}>
            <div style={{ fontSize: '20px', fontWeight: 'bold', color: '#16a34a' }}>
              {createdParentsCount}
            </div>
            <div style={{ color: '#15803d', marginTop: '2px', fontSize: '11px' }}>
              Pais
            </div>
          </div>
          
          <div style={{ background: '#eff6ff', border: '1px solid #93c5fd', borderRadius: '8px', padding: '12px', textAlign: 'center' }}>
            <div style={{ fontSize: '20px', fontWeight: 'bold', color: '#2563eb' }}>
              {createdVariationsCount}
            </div>
            <div style={{ color: '#1e40af', marginTop: '2px', fontSize: '11px' }}>
              Variações
            </div>
          </div>
          
          <div style={{ background: '#fef3c7', border: '1px solid #fcd34d', borderRadius: '8px', padding: '12px', textAlign: 'center' }}>
            <div style={{ fontSize: '20px', fontWeight: 'bold', color: '#d97706' }}>
              {createdBasesCount}
            </div>
            <div style={{ color: '#b45309', marginTop: '2px', fontSize: '11px' }}>
              Bases
            </div>
          </div>
          
          <div style={{ background: '#f3e8ff', border: '1px solid #c084fc', borderRadius: '8px', padding: '12px', textAlign: 'center' }}>
            <div style={{ fontSize: '20px', fontWeight: 'bold', color: '#9333ea' }}>
              {updatedDisplayCount}
            </div>
            <div style={{ color: '#7e22ce', marginTop: '2px', fontSize: '11px' }}>
              Atualizados
            </div>
          </div>

          <div style={{ background: '#fff7ed', border: '1px solid #fdba74', borderRadius: '8px', padding: '12px', textAlign: 'center' }}>
            <div style={{ fontSize: '20px', fontWeight: 'bold', color: '#c2410c' }}>
              {removedVariationsCount}
            </div>
            <div style={{ color: '#9a3412', marginTop: '2px', fontSize: '11px' }}>
              Removidas
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
                  <div>
                    <span style={{ fontWeight: '600' }}>{item.sku}</span>
                    <span style={{ fontSize: '12px', color: '#6b7280', marginLeft: '8px' }}>
                      {item.entity}
                    </span>
                    <div style={{ fontSize: '12px', color: '#1e3a8a', marginTop: '4px' }}>
                      Mantidas/selecionadas: {Number(item.selected_variations_count || item.variations_count || 0)}
                      {' • '}
                      Removidas: {Number(item.removed_variations_count || 0)}
                      {' • '}
                      Deletadas no Bling: {Number(item.removed_variations_deleted_count || 0)}
                    </div>
                    {Array.isArray(item.removed_variations) && item.removed_variations.length > 0 && (
                      <div style={{ fontSize: '11px', color: '#9a3412', marginTop: '4px' }}>
                        Excluídas: {item.removed_variations.join(', ')}
                      </div>
                    )}
                    {Array.isArray(item.removed_variations_delete_failed) && item.removed_variations_delete_failed.length > 0 && (
                      <div style={{ fontSize: '11px', color: '#991b1b', marginTop: '4px', background: '#fee2e2', borderRadius: '4px', padding: '4px 6px' }}>
                        Falha ao excluir: {item.removed_variations_delete_failed.join(' | ')}
                      </div>
                    )}
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}

        {failedItems.length > 0 && (
          <div style={{ marginBottom: '20px' }}>
            <h4 style={{ marginBottom: '12px', color: '#dc2626' }}>✗ Falhas ({failedItems.length}):</h4>
            <div style={{ background: '#fef2f2', borderRadius: '6px', padding: '12px', maxHeight: '300px', overflowY: 'auto' }}>
              {failedItems.map((item, idx) => {
                const isOrphan = item.error_type === 'orphan_composition_variations';
                const errorText = item.error || item.error_message || item.message || item.detail;
                const isDuplicateCodeError =
                  typeof errorText === 'string' &&
                  errorText.toLowerCase().includes('já foi cadastrado');
                return (
                  <div key={idx} style={{ padding: '10px 0', fontSize: '14px', borderBottom: '1px solid #fecaca' }}>
                    <div style={{ color: '#dc2626' }}>
                      • {item.sku} <span style={{ fontSize: '12px', color: '#991b1b' }}>({item.entity})</span>
                    </div>
                    {isOrphan ? (
                      <div style={{ marginTop: '8px', marginLeft: '16px', background: '#fff7ed', border: '1px solid #fed7aa', borderRadius: '6px', padding: '10px' }}>
                        <div style={{ fontWeight: 600, color: '#9a3412', marginBottom: '6px', fontSize: '13px' }}>
                          ⚠️ Variações com composição inválida no Bling
                        </div>
                        <div style={{ color: '#7c2d12', fontSize: '12px', marginBottom: '8px' }}>
                          O produto <strong>{item.sku}</strong> possui {item.orphan_variations?.length || 'algumas'} variação(ões) que foram criadas
                          em execuções anteriores com formato "Com composição" mas sem componentes definidos.
                          O Bling não aceita atualizar o produto enquanto essas variações existirem.
                        </div>
                        <div style={{ color: '#7c2d12', fontSize: '12px', marginBottom: '8px' }}>
                          <strong>Como corrigir:</strong>
                          <ol style={{ margin: '6px 0 0 16px', padding: 0 }}>
                            <li>Acesse o produto <strong>{item.sku}</strong> (ID: {item.bling_product_id}) no Bling</li>
                            <li>Vá em Variações e localize as variações problemáticas</li>
                            <li>Exclua as variações listadas abaixo</li>
                            <li>Execute o plano novamente</li>
                          </ol>
                        </div>
                        {item.orphan_variations?.length > 0 && (
                          <div style={{ background: '#fee2e2', borderRadius: '4px', padding: '6px 8px' }}>
                            <div style={{ fontSize: '11px', color: '#991b1b', fontWeight: 600, marginBottom: '4px' }}>Variações a excluir no Bling:</div>
                            {item.orphan_variations.map((v, i) => (
                              <div key={i} style={{ fontSize: '12px', color: '#7f1d1d', fontFamily: 'monospace' }}>• {v}</div>
                            ))}
                          </div>
                        )}
                      </div>
                    ) : (
                      errorText && (
                        <div style={{ marginTop: '4px', marginLeft: '16px' }}>
                          <div style={{ fontSize: '12px', color: '#991b1b', background: '#fee2e2', padding: '6px', borderRadius: '4px' }}>
                            {errorText}
                          </div>
                          {isDuplicateCodeError && (
                            <div style={{ marginTop: '6px', fontSize: '12px', color: '#7f1d1d', background: '#fff7ed', border: '1px solid #fed7aa', padding: '8px', borderRadius: '4px' }}>
                              Esse erro indica conflito de SKU no Bling.
                              Verifique se o produto pai já existe e se as variações já estão cadastradas.
                              Nesse caso, o fluxo correto costuma ser atualizar o pai existente em vez de criar um novo pai com os mesmos SKUs de variação.
                            </div>
                          )}
                        </div>
                      )
                    )}
                  </div>
                );
              })}
            </div>

            {failedUpdateItems.length > 0 && executedPlan && onRecreateFailedUpdates && (
              <div style={{ marginTop: '12px' }}>
                <button
                  type="button"
                  onClick={async () => {
                    const skus = failedUpdateItems.map(item => item.sku).filter(Boolean);
                    const recreateResult = await onRecreateFailedUpdates(skus);
                    if (recreateResult) {
                      onClose();
                    }
                  }}
                  style={{
                    width: '100%',
                    padding: '10px 12px',
                    border: '1px solid #f59e0b',
                    borderRadius: '6px',
                    background: '#f59e0b',
                    color: '#fff',
                    fontWeight: 600,
                    cursor: 'pointer',
                  }}
                >
                  Apagar e recriar itens com falha de atualizacao
                </button>
              </div>
            )}
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
