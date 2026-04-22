import React, { useState, useEffect } from 'react';
import { Layout } from '../../components/Layout';
import useIsMobile from '../../hooks/useIsMobile';

const API_BASE = '/api';
const PRODUCTS_CACHE_KEY = 'smartb_products_catalog_v3';

function loadCachedCatalog() {
  try {
    const raw = localStorage.getItem(PRODUCTS_CACHE_KEY);
    if (!raw) return null;
    const parsed = JSON.parse(raw);
    return Array.isArray(parsed) ? parsed : null;
  } catch (_) {
    return null;
  }
}

function matchesProductQuery(product, query) {
  const normalized = (query || '').trim().toLowerCase();
  if (!normalized) return true;

  const codigo = String(product?.codigo || '').toLowerCase();
  const nome = String(product?.nome || '').toLowerCase();
  const id = String(product?.id || '').toLowerCase();
  return codigo.includes(normalized) || nome.includes(normalized) || id.includes(normalized);
}

function searchFromCachedCatalog(query, limit = 20) {
  const catalog = loadCachedCatalog();
  if (!catalog || catalog.length === 0) return null;

  return catalog
    .filter((item) => matchesProductQuery(item, query))
    .slice(0, limit);
}

// ============ Models Page ============

export function ModelsPage() {
  const isMobile = useIsMobile(768);
  const [models, setModels] = useState([]);
  const [loading, setLoading] = useState(false);
  const [showForm, setShowForm] = useState(false);
  const [editingCode, setEditingCode] = useState(null);
  const [error, setError] = useState(null);
  const [confirmDeleteModel, setConfirmDeleteModel] = useState(null);

  const [formData, setFormData] = useState({
    code: '',
    name: '',
    allowed_sizes: [],
    size_order: [],
  });
  const [dragIndex, setDragIndex] = useState(null);

  const [sizeInput, setSizeInput] = useState('');

  useEffect(() => {
    fetchModels();
  }, []);

  async function fetchModels() {
    try {
      setLoading(true);
      const resp = await fetch(`${API_BASE}/config/models`);
      if (!resp.ok) throw new Error('Failed to fetch models');
      const data = await resp.json();
      setModels(data);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }

  function handleAddSize() {
    if (sizeInput && !formData.allowed_sizes.includes(sizeInput)) {
      const newAllowed = [...formData.allowed_sizes, sizeInput];
      const newOrder = Array.isArray(formData.size_order) && formData.size_order.length > 0
        ? [...formData.size_order, sizeInput]
        : [...newAllowed];
      setFormData({
        ...formData,
        allowed_sizes: newAllowed,
        size_order: newOrder,
      });
      setSizeInput('');
    }
  }

  function handleRemoveSize(size) {
    const newAllowed = formData.allowed_sizes.filter(s => s !== size);
    const newOrder = (formData.size_order || []).filter(s => s !== size);
    setFormData({
      ...formData,
      allowed_sizes: newAllowed,
      size_order: newOrder,
    });
  }

  async function handleSubmit(e) {
    e.preventDefault();
    try {
      const url = editingCode
        ? `${API_BASE}/config/models/${editingCode}`
        : `${API_BASE}/config/models`;
      const method = editingCode ? 'PUT' : 'POST';

      const resp = await fetch(url, {
        method,
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(formData),
      });

      if (!resp.ok) {
        const err = await resp.json();
        throw new Error(err.detail?.message || 'Failed to save model');
      }

      setShowForm(false);
      setEditingCode(null);
      setFormData({ code: '', name: '', allowed_sizes: [], size_order: [] });
      fetchModels();
    } catch (err) {
      setError(err.message);
    }
  }

  function handleEdit(model) {
    setFormData({
      ...model,
      size_order: model.size_order && model.size_order.length > 0 ? model.size_order : model.allowed_sizes,
    });
    setEditingCode(model.code);
    setShowForm(true);
  }

  async function handleDeleteModel(code) {
    try {
      const resp = await fetch(`${API_BASE}/config/models/${code}`, { method: 'DELETE' });
      if (!resp.ok) {
        const err = await resp.json().catch(() => ({}));
        throw new Error(err.detail?.message || 'Falha ao excluir o modelo');
      }
      setConfirmDeleteModel(null);
      fetchModels();
    } catch (err) {
      setError(err.message);
    }
  }

  return (
    <Layout>
      <div className="page-inner">
      <h2>Modelos</h2>
      {error && <div className="error">{error}</div>}
      
      <button onClick={() => { setShowForm(!showForm); setEditingCode(null); }}>
        {showForm ? 'Cancelar' : 'Novo Modelo'}
      </button>

      {showForm && (
        <form onSubmit={handleSubmit} className="form">
          <input
            type="text"
            placeholder="Código (ex: CAM)"
            value={formData.code}
            onChange={(e) => setFormData({ ...formData, code: e.target.value })}
            disabled={!!editingCode}
            required
          />
          <input
            type="text"
            placeholder="Nome (ex: Camiseta)"
            value={formData.name}
            onChange={(e) => setFormData({ ...formData, name: e.target.value })}
            required
          />
          <div>
            <label>Tamanhos Permitidos:</label>
            <div className="size-input">
              <input
                type="text"
                placeholder="Adicionar tamanho"
                value={sizeInput}
                onChange={(e) => setSizeInput(e.target.value)}
                onKeyPress={(e) => e.key === 'Enter' && (e.preventDefault(), handleAddSize())}
              />
              <button type="button" onClick={handleAddSize}>+</button>
            </div>
            <div className="chips">
              {formData.allowed_sizes.map((size, idx) => (
                <span
                  key={size}
                  className={`chip draggable-chip ${dragIndex === idx ? 'dragging' : ''}`}
                  draggable
                  onDragStart={() => setDragIndex(idx)}
                  onDragOver={(e) => e.preventDefault()}
                  onDrop={() => {
                    if (dragIndex === null || dragIndex === idx) return;
                    const newAllowed = [...formData.allowed_sizes];
                    const [moved] = newAllowed.splice(dragIndex, 1);
                    newAllowed.splice(idx, 0, moved);
                    setDragIndex(null);
                    setFormData({
                      ...formData,
                      allowed_sizes: newAllowed,
                      size_order: [...newAllowed],
                    });
                  }}
                  onDragEnd={() => setDragIndex(null)}
                >
                  {size} <button type="button" onClick={() => handleRemoveSize(size)}>×</button>
                </span>
              ))}
            </div>
          </div>
          <button type="submit">Salvar</button>
        </form>
      )}

      {loading ? <p>Carregando...</p> : (
        isMobile ? (
          <div style={{ display: 'grid', gap: 12 }}>
            {models.map((model) => (
              <div key={model.id} style={{ border: '1px solid #e2e8f0', borderRadius: 10, background: '#fff', padding: 14 }}>
                <div style={{ fontWeight: 700, color: '#0f172a', marginBottom: 6 }}>{model.code} • {model.name}</div>
                <div style={{ fontSize: 13, color: '#64748b', marginBottom: 10 }}><strong>Tamanhos:</strong> {model.allowed_sizes.join(', ')}</div>
                <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
                  <button onClick={() => handleEdit(model)}>Editar</button>
                  <button style={{ background: '#dc2626' }} onClick={() => setConfirmDeleteModel({ code: model.code, name: model.name })}>Excluir</button>
                </div>
              </div>
            ))}
          </div>
        ) : (
          <table className="table">
            <thead>
              <tr>
                <th>Código</th>
                <th>Nome</th>
                <th>Tamanhos</th>
                <th>Ações</th>
              </tr>
            </thead>
            <tbody>
              {models.map(model => (
                <tr key={model.id}>
                  <td>{model.code}</td>
                  <td>{model.name}</td>
                  <td>{model.allowed_sizes.join(', ')}</td>
                  <td>
                    <div style={{ display: 'flex', gap: '8px' }}>
                      <button onClick={() => handleEdit(model)}>Editar</button>
                      <button style={{ background: '#dc2626' }} onClick={() => setConfirmDeleteModel({ code: model.code, name: model.name })}>Excluir</button>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )
      )}

      {confirmDeleteModel && (
        <div className="modal-overlay" onClick={() => setConfirmDeleteModel(null)}>
          <div className="modal" onClick={(e) => e.stopPropagation()}>
            <h3>Confirmar exclusão</h3>
            <p>Tem certeza que deseja excluir o modelo <strong>{confirmDeleteModel.name}</strong> ({confirmDeleteModel.code})?</p>
            <p className="helper-text">Esta ação desativa o modelo e pode afetar configurações dependentes.</p>
            <div className="modal-actions">
              <button onClick={() => setConfirmDeleteModel(null)} style={{ background: '#64748b' }}>Cancelar</button>
              <button onClick={() => handleDeleteModel(confirmDeleteModel.code)} style={{ background: '#dc2626' }}>Excluir</button>
            </div>
          </div>
        </div>
      )}
      </div>
    </Layout>
  );
}

// ============ Colors Page ============

export function ColorsPage() {
  const isMobile = useIsMobile(768);
  const [colors, setColors] = useState([]);
  const [loading, setLoading] = useState(false);
  const [showForm, setShowForm] = useState(false);
  const [editingCode, setEditingCode] = useState(null);

  // Drag-and-drop reorder is handled on the chips directly
  const [error, setError] = useState(null);
  const [confirmDeleteColor, setConfirmDeleteColor] = useState(null);

  const [formData, setFormData] = useState({
    code: '',
    name: '',
  });

  useEffect(() => {
    fetchColors();
  }, []);

  async function fetchColors() {
    try {
      setLoading(true);
      const resp = await fetch(`${API_BASE}/config/colors`);
      if (!resp.ok) throw new Error('Failed to fetch colors');
      const data = await resp.json();
      setColors(data);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }

  async function handleSubmit(e) {
    e.preventDefault();
    try {
      const url = editingCode
        ? `${API_BASE}/config/colors/${editingCode}`
        : `${API_BASE}/config/colors`;
      const method = editingCode ? 'PUT' : 'POST';

      const resp = await fetch(url, {
        method,
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(formData),
      });

      if (!resp.ok) {
        const err = await resp.json();
        throw new Error(err.detail?.message || 'Failed to save color');
      }

      setShowForm(false);
      setEditingCode(null);
      setFormData({ code: '', name: '' });
      fetchColors();
    } catch (err) {
      setError(err.message);
    }
  }

  function handleEdit(color) {
    setFormData({ code: color.code, name: color.name });
    setEditingCode(color.code);
    setShowForm(true);
  }

  async function handleDeleteColor(code) {
    try {
      const resp = await fetch(`${API_BASE}/config/colors/${code}`, { method: 'DELETE' });
      if (!resp.ok) {
        const err = await resp.json().catch(() => ({}));
        throw new Error(err.detail?.message || 'Falha ao excluir a cor');
      }
      setConfirmDeleteColor(null);
      fetchColors();
    } catch (err) {
      setError(err.message);
    }
  }

  return (
    <Layout>
      <div className="page-inner">
      <h2>Cores</h2>
      {error && <div className="error">{error}</div>}
      
      <button onClick={() => { setShowForm(!showForm); setEditingCode(null); }}>
        {showForm ? 'Cancelar' : 'Nova Cor'}
      </button>

      {showForm && (
        <form onSubmit={handleSubmit} className="form">
          <input
            type="text"
            placeholder="Código (ex: BR)"
            value={formData.code}
            onChange={(e) => setFormData({ ...formData, code: e.target.value })}
            disabled={!!editingCode}
            required
          />
          <input
            type="text"
            placeholder="Nome (ex: Branca)"
            value={formData.name}
            onChange={(e) => setFormData({ ...formData, name: e.target.value })}
            required
          />
          <button type="submit">Salvar</button>
        </form>
      )}

      {loading ? <p>Carregando...</p> : (
        isMobile ? (
          <div style={{ display: 'grid', gap: 12 }}>
            {colors.map((color) => (
              <div key={color.id} style={{ border: '1px solid #e2e8f0', borderRadius: 10, background: '#fff', padding: 14 }}>
                <div style={{ fontWeight: 700, color: '#0f172a', marginBottom: 6 }}>{color.code} • {color.name}</div>
                <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
                  <button onClick={() => handleEdit(color)}>Editar</button>
                  <button style={{ background: '#dc2626' }} onClick={() => setConfirmDeleteColor({ code: color.code, name: color.name })}>Excluir</button>
                </div>
              </div>
            ))}
          </div>
        ) : (
          <table className="table">
            <thead>
              <tr>
                <th>Código</th>
                <th>Nome</th>
                <th>Ações</th>
              </tr>
            </thead>
            <tbody>
              {colors.map(color => (
                <tr key={color.id}>
                  <td>{color.code}</td>
                  <td>{color.name}</td>
                  <td>
                    <div style={{ display: 'flex', gap: '8px' }}>
                      <button onClick={() => handleEdit(color)}>Editar</button>
                      <button style={{ background: '#dc2626' }} onClick={() => setConfirmDeleteColor({ code: color.code, name: color.name })}>Excluir</button>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )
      )}

      {confirmDeleteColor && (
        <div className="modal-overlay" onClick={() => setConfirmDeleteColor(null)}>
          <div className="modal" onClick={(e) => e.stopPropagation()}>
            <h3>Confirmar exclusão</h3>
            <p>Tem certeza que deseja excluir a cor <strong>{confirmDeleteColor.name}</strong> ({confirmDeleteColor.code})?</p>
            <p className="helper-text">Esta ação desativa a cor e pode afetar configurações dependentes.</p>
            <div className="modal-actions">
              <button onClick={() => setConfirmDeleteColor(null)} style={{ background: '#64748b' }}>Cancelar</button>
              <button onClick={() => handleDeleteColor(confirmDeleteColor.code)} style={{ background: '#dc2626' }}>Excluir</button>
            </div>
          </div>
        </div>
      )}
      </div>
    </Layout>
  );
}

// ============ Templates Page ============

export function TemplatesPage() {
  const isMobile = useIsMobile(768);
  const [templates, setTemplates] = useState([]);
  const [models, setModels] = useState([]);
  const [searchResults, setSearchResults] = useState([]);
  const [loading, setLoading] = useState(false);
  const [searching, setSearching] = useState(false);
  const [error, setError] = useState(null);

  const [selectedModel, setSelectedModel] = useState('');
  const [templateKind, setTemplateKind] = useState('BASE_PLAIN');
  const [searchQuery, setSearchQuery] = useState('');
  const [showReauthModal, setShowReauthModal] = useState(false);
  const [pendingRetryAfterReauth, setPendingRetryAfterReauth] = useState(false);
  const [infoBoxExpanded, setInfoBoxExpanded] = useState(false);
  const [editingTemplate, setEditingTemplate] = useState(null);
  const [confirmDeleteTemplate, setConfirmDeleteTemplate] = useState(null);

  useEffect(() => {
    fetchModels();
    fetchTemplates();
  }, []);

  async function fetchModels() {
    try {
      const resp = await fetch(`${API_BASE}/config/models`);
      if (!resp.ok) throw new Error('Failed to fetch models');
      const data = await resp.json();
      setModels(data);
    } catch (err) {
      setError(err.message);
    }
  }

  async function fetchTemplates() {
    try {
      setLoading(true);
      const url = selectedModel
        ? `${API_BASE}/config/templates?model_code=${selectedModel}`
        : `${API_BASE}/config/templates`;
      const resp = await fetch(url);
      if (!resp.ok) throw new Error('Failed to fetch templates');
      const data = await resp.json();

      const sortByModel = (list) => [...list].sort((a, b) => {
        const modelCompare = (a.model_code || '').localeCompare(b.model_code || '', 'pt-BR', { sensitivity: 'base' });
        if (modelCompare !== 0) return modelCompare;
        return (a.template_kind || '').localeCompare(b.template_kind || '', 'pt-BR', { sensitivity: 'base' });
      });
      
      // Filter out templates from inactive models only if models are loaded
      if (models && models.length > 0) {
        const activeModelCodes = models.filter(m => m.is_active).map(m => m.code);
        const filteredTemplates = data.filter(t => activeModelCodes.includes(t.model_code));
        setTemplates(sortByModel(filteredTemplates));
      } else {
        setTemplates(sortByModel(data));
      }
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }

  async function handleSearch() {
    const q = searchQuery.trim();
    if (!q) {
      setSearchResults([]);
      return;
    }

    try {
      setSearching(true);
      setError(null);

      // Same behavior as campaign search: instant local filter when catalog cache exists.
      const cachedResults = searchFromCachedCatalog(q, 20);
      if (cachedResults) {
        setSearchResults(cachedResults);
        return;
      }

      const resp = await fetch(
        `${API_BASE}/bling/products/list/all?q=${encodeURIComponent(q)}&page=1&limit=20&include_hierarchy=false`
      );
      
      if (!resp.ok) {
        const err = await resp.json();
        const errorMsg = err.detail?.message || 'Erro ao buscar produtos no Bling';
        const needsReauth = err.detail?.needs_reauth || resp.status === 401;
        
        // If token expired, show reauth modal
        if (needsReauth || errorMsg.includes('Token') || errorMsg.includes('expirado') || errorMsg.includes('401')) {
          setError(errorMsg);
          setShowReauthModal(true);
        } else {
          throw new Error(errorMsg);
        }
      } else {
        const data = await resp.json();
        setSearchResults(data.items || []);
        
        if (!data.items || data.items.length === 0) {
          setError(`Nenhum produto encontrado com "${q}". Verifique se o produto existe no Bling.`);
        }
      }
    } catch (err) {
      setError(err.message);
      setSearchResults([]);
    } finally {
      setSearching(false);
    }
  }

  async function handleSelectProduct(product) {
    if (!selectedModel) {
      setError('Selecione um modelo primeiro');
      return;
    }

    try {
      const resp = await fetch(`${API_BASE}/config/templates`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          model_code: selectedModel,
          template_kind: templateKind,
          bling_product_id: product.id,
          bling_product_sku: product.codigo,
          bling_product_name: product.nome,
        }),
      });

      if (!resp.ok) {
        const err = await resp.json();
        throw new Error(err.detail?.message || 'Failed to create template');
      }

      setSearchQuery('');
      setSearchResults([]);
      setEditingTemplate(null);
      fetchTemplates();
    } catch (err) {
      setError(err.message);
    }
  }

  function handleEditTemplate(template) {
    setEditingTemplate(template);
    setSelectedModel(template.model_code);
    setTemplateKind(template.template_kind);
    setError(null);
    setSearchResults([]);
    setSearchQuery(template.bling_product_sku || template.bling_product_name || '');
    window.scrollTo({ top: 0, behavior: 'smooth' });
  }

  async function handleDeleteTemplate(templateId) {
    try {
      const resp = await fetch(`${API_BASE}/config/templates/${templateId}`, {
        method: 'DELETE',
      });

      if (!resp.ok) {
        const err = await resp.json().catch(() => ({}));
        throw new Error(err.detail?.message || 'Falha ao excluir template');
      }

      setConfirmDeleteTemplate(null);
      if (editingTemplate?.id === templateId) {
        setEditingTemplate(null);
      }
      fetchTemplates();
    } catch (err) {
      setError(err.message);
    }
  }

  function handleBackFromTemplateForm() {
    setEditingTemplate(null);
    setSelectedModel('');
    setTemplateKind('BASE_PLAIN');
    setSearchQuery('');
    setSearchResults([]);
    setError(null);
  }

  useEffect(() => {
    if (models.length > 0) {
      fetchTemplates();
    }
  }, [selectedModel, models]);

  return (
    <Layout>
      <div className="page-inner">
      <h2>Templates de Produtos</h2>
      
      <div className="info-box" style={{ cursor: 'pointer' }}>
        <div onClick={() => setInfoBoxExpanded(!infoBoxExpanded)} style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <p><strong>📋 O que são Templates?</strong></p>
          <span style={{ fontSize: '1.2rem', transition: 'transform 0.3s ease', transform: infoBoxExpanded ? 'rotate(180deg)' : 'rotate(0deg)' }}>▼</span>
        </div>
        {infoBoxExpanded && (
          <div style={{ marginTop: '12px' }}>
            <p>Templates são produtos <strong>base do Bling</strong> que servem como referência para criar variações.</p>
            <p><strong>Exemplo prático:</strong></p>
            <ul>
              <li><strong>Base Lisa:</strong> Camiseta lisa sem estampa (produto base)</li>
              <li><strong>Principal Estampado:</strong> Camiseta com estampa (produto pai no Bling)</li>
              <li><strong>Variação Estampada:</strong> Cada cor/tamanho específico (P Branca, M Preta, etc.)</li>
            </ul>
            <p>Para cada <strong>modelo</strong> (ex: CAM - Camiseta) você precisa associar produtos do Bling aos tipos de template.</p>
          </div>
        )}
      </div>

      {error && <div className="error">{error}</div>}

      <div className="section">
        <h3>1️⃣ Selecione o Modelo</h3>
        <p className="helper-text">Escolha qual modelo você quer configurar (ex: Camiseta, Moletom, etc.)</p>
        <select value={selectedModel} onChange={(e) => setSelectedModel(e.target.value)}>
          <option value="">-- Selecione um modelo --</option>
          {models.map(m => (
            <option key={m.id} value={m.code}>{m.name} ({m.code})</option>
          ))}
        </select>
      </div>

      {selectedModel && (
        <div className="section">
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: 12, flexWrap: 'wrap' }}>
            <h3 style={{ margin: 0 }}>2️⃣ Associar Produto do Bling como Template</h3>
            <button type="button" onClick={handleBackFromTemplateForm} style={{ background: '#64748b' }}>
              ← Voltar
            </button>
          </div>
          <p className="helper-text">
            Modelo selecionado: <strong>{models.find(m => m.code === selectedModel)?.name}</strong>
          </p>
          
          <div style={{ marginBottom: '16px' }}>
            <label style={{ display: 'block', marginBottom: '8px', fontWeight: 500 }}>
              Tipo de Template:
            </label>
            <select value={templateKind} onChange={(e) => setTemplateKind(e.target.value)}>
              <option value="BASE_PLAIN">Base Lisa - Produto base sem estampa</option>
              <option value="PARENT_PRINTED">Principal Estampado - Produto pai com estampa</option>
              <option value="VARIATION_PRINTED">Variação Estampada - Variação específica (cor/tamanho)</option>
            </select>
          </div>

          {editingTemplate && (
            <div className="info-box" style={{ marginBottom: '16px', background: '#fff7ed', borderColor: '#fdba74' }}>
              <p style={{ marginBottom: 8 }}>
                <strong>✏️ Editando Template:</strong> {editingTemplate.model_code} / {
                  editingTemplate.template_kind === 'BASE_PLAIN' ? 'Base Lisa' :
                  editingTemplate.template_kind === 'PARENT_PRINTED' ? 'Principal Estampado' :
                  editingTemplate.template_kind === 'VARIATION_PRINTED' ? 'Variação Estampada' :
                  editingTemplate.template_kind
                }
              </p>
              <p style={{ marginBottom: 12, fontSize: 14, color: '#7c2d12' }}>
                Selecione um novo produto abaixo e clique em "Usar este Produto" para atualizar o template.
              </p>
              <button
                type="button"
                onClick={() => setEditingTemplate(null)}
                style={{ background: '#64748b' }}
              >
                Cancelar edição
              </button>
            </div>
          )}

          <div className="search-box">
            <input
              type="text"
              placeholder="Digite o nome ou SKU do produto no Bling..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              onKeyPress={(e) => e.key === 'Enter' && handleSearch()}
            />
            <button onClick={handleSearch} disabled={searching}>
              {searching ? 'Buscando...' : '🔍 Buscar no Bling'}
            </button>
          </div>

          {searchResults.length > 0 && (
            <div className="search-results">
              <p style={{ padding: '12px 16px', background: '#f8fafc', fontWeight: 500, borderBottom: '1px solid #e2e8f0' }}>
                {searchResults.length} produto(s) encontrado(s):
              </p>
              {searchResults.map(product => (
                <div key={product.id} className="result-item">
                  <div>
                    <strong>{product.nome}</strong>
                    <p>SKU: {product.codigo}</p>
                    <p>ID Bling: {product.id}</p>
                  </div>
                  <button onClick={() => handleSelectProduct(product)}>
                    ✓ Usar este Produto
                  </button>
                </div>
              ))}
            </div>
          )}
        </div>
      )}

      <div className="section">
        <h3>📋 Templates Configurados</h3>
        {loading ? <p>Carregando...</p> : (
          templates.length === 0 ? (
            <p>Nenhum template configurado.</p>
          ) : (
            isMobile ? (
              <div style={{ display: 'grid', gap: 12 }}>
                {templates.map((t) => (
                  <div key={t.id} style={{ border: '1px solid #e2e8f0', borderRadius: 10, background: '#fff', padding: 14 }}>
                    <div style={{ fontWeight: 700, color: '#0f172a', marginBottom: 6 }}>{t.model_code} • {t.bling_product_name}</div>
                    <div style={{ fontSize: 12, color: '#64748b', marginBottom: 4 }}><strong>Tipo:</strong> {
                      t.template_kind === 'BASE_PLAIN' ? 'Base Lisa' :
                      t.template_kind === 'PARENT_PRINTED' ? 'Principal Estampado' :
                      t.template_kind === 'VARIATION_PRINTED' ? 'Variação Estampada' :
                      t.template_kind
                    }</div>
                    <div style={{ fontSize: 12, color: '#475569', marginBottom: 10 }}><strong>SKU:</strong> {t.bling_product_sku}</div>
                    <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
                      <button type="button" onClick={() => handleEditTemplate(t)}>Editar</button>
                      <button
                        type="button"
                        style={{ background: '#dc2626' }}
                        onClick={() => setConfirmDeleteTemplate(t)}
                      >
                        Excluir
                      </button>
                    </div>
                  </div>
                ))}
              </div>
            ) : (
              <table className="table">
                <thead>
                  <tr>
                    <th>Modelo</th>
                    <th>Tipo</th>
                    <th>SKU Bling</th>
                    <th>Nome Bling</th>
                    <th>Ações</th>
                  </tr>
                </thead>
                <tbody>
                  {templates.map(t => (
                    <tr key={t.id}>
                      <td>{t.model_code}</td>
                      <td>{
                        t.template_kind === 'BASE_PLAIN' ? 'Base Lisa' :
                        t.template_kind === 'PARENT_PRINTED' ? 'Principal Estampado' :
                        t.template_kind === 'VARIATION_PRINTED' ? 'Variação Estampada' :
                        t.template_kind
                      }</td>
                      <td>{t.bling_product_sku}</td>
                      <td>{t.bling_product_name}</td>
                      <td>
                        <div style={{ display: 'flex', gap: '8px' }}>
                          <button type="button" onClick={() => handleEditTemplate(t)}>Editar</button>
                          <button
                            type="button"
                            style={{ background: '#dc2626' }}
                            onClick={() => setConfirmDeleteTemplate(t)}
                          >
                            Excluir
                          </button>
                        </div>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )
          )
        )}
      </div>

      {confirmDeleteTemplate && (
        <div className="modal-overlay" onClick={() => setConfirmDeleteTemplate(null)}>
          <div className="modal" onClick={(e) => e.stopPropagation()}>
            <h3>Confirmar exclusão</h3>
            <p>
              Tem certeza que deseja excluir o template <strong>{confirmDeleteTemplate.model_code}</strong> / <strong>{
                confirmDeleteTemplate.template_kind === 'BASE_PLAIN' ? 'Base Lisa' :
                confirmDeleteTemplate.template_kind === 'PARENT_PRINTED' ? 'Principal Estampado' :
                confirmDeleteTemplate.template_kind === 'VARIATION_PRINTED' ? 'Variação Estampada' :
                confirmDeleteTemplate.template_kind
              }</strong>?
            </p>
            <p className="helper-text">Esta ação remove o vínculo com o produto do Bling.</p>
            <div className="modal-actions">
              <button onClick={() => setConfirmDeleteTemplate(null)} style={{ background: '#64748b' }}>Cancelar</button>
              <button onClick={() => handleDeleteTemplate(confirmDeleteTemplate.id)} style={{ background: '#dc2626' }}>Excluir</button>
            </div>
          </div>
        </div>
      )}

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
                    window.open(`${API_BASE}/auth/bling/connect`, '_blank');
                    setPendingRetryAfterReauth(true);
                    setError('Autenticando no Bling...');
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
                    // Retry the search
                    handleSearch();
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
      </div>
    </Layout>
  );
}
