import React, { useEffect, useMemo, useState } from 'react';
import { Layout } from '../../components/Layout';

const API_BASE = '/api';

function formatDate(value) {
  if (!value) return '—';
  return new Date(value).toLocaleDateString('pt-BR');
}

export function EventCreatePage() {
  const [events, setEvents] = useState([]);
  const [loadingEvents, setLoadingEvents] = useState(false);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState(null);
  const [success, setSuccess] = useState(null);

  const [name, setName] = useState('');
  const [startDate, setStartDate] = useState('');
  const [endDate, setEndDate] = useState('');

  const [productQuery, setProductQuery] = useState('');
  const [searchingProducts, setSearchingProducts] = useState(false);
  const [productResults, setProductResults] = useState([]);
  const [selectedProducts, setSelectedProducts] = useState([]);
  const [editingEventId, setEditingEventId] = useState(null);

  async function loadEvents() {
    try {
      setLoadingEvents(true);
      const resp = await fetch(`${API_BASE}/events`);
      if (!resp.ok) throw new Error('Falha ao carregar eventos');
      const data = await resp.json();
      setEvents(Array.isArray(data) ? data : []);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoadingEvents(false);
    }
  }

  useEffect(() => {
    loadEvents();
  }, []);

  async function searchProducts() {
    const q = productQuery.trim();
    if (!q) {
      setProductResults([]);
      return;
    }

    try {
      setSearchingProducts(true);
      const resp = await fetch(`${API_BASE}/bling/products/search?q=${encodeURIComponent(q)}&page=1&limit=20`);
      if (!resp.ok) throw new Error('Falha ao buscar produtos');
      const data = await resp.json();
      setProductResults(data.items || []);
    } catch (err) {
      setError(err.message);
      setProductResults([]);
    } finally {
      setSearchingProducts(false);
    }
  }

  const selectedSkuSet = useMemo(
    () => new Set(selectedProducts.map((p) => String(p.sku || '').toUpperCase())),
    [selectedProducts]
  );

  function addProduct(product) {
    const sku = String(product.codigo || '').toUpperCase().trim();
    if (!sku || selectedSkuSet.has(sku)) return;

    setSelectedProducts((prev) => [
      ...prev,
      {
        bling_product_id: product.id,
        sku,
        product_name: product.nome || sku,
      },
    ]);
  }

  function removeProduct(sku) {
    setSelectedProducts((prev) => prev.filter((p) => p.sku !== sku));
  }

  function resetForm() {
    setEditingEventId(null);
    setName('');
    setStartDate('');
    setEndDate('');
    setSelectedProducts([]);
    setProductResults([]);
    setProductQuery('');
  }

  async function handleEdit(eventId) {
    try {
      setError(null);
      const resp = await fetch(`${API_BASE}/events/${eventId}`);
      if (!resp.ok) throw new Error('Falha ao carregar evento');
      const event = await resp.json();

      setEditingEventId(event.id);
      setName(event.name || '');
      setStartDate(event.start_date || '');
      setEndDate(event.end_date || '');
      setSelectedProducts(
        (event.products || []).map((p) => ({
          bling_product_id: p.bling_product_id,
          sku: p.sku,
          product_name: p.product_name,
        }))
      );
      setSuccess(null);
    } catch (err) {
      setError(err.message);
    }
  }

  async function handleDelete(eventId) {
    const ok = window.confirm('Deseja realmente excluir este evento?');
    if (!ok) return;

    try {
      setError(null);
      const resp = await fetch(`${API_BASE}/events/${eventId}`, { method: 'DELETE' });
      if (!resp.ok) throw new Error('Falha ao excluir evento');

      if (editingEventId === eventId) {
        resetForm();
      }

      setSuccess('Evento excluído com sucesso');
      await loadEvents();
    } catch (err) {
      setError(err.message);
    }
  }

  async function handleSubmit(e) {
    e.preventDefault();
    setError(null);
    setSuccess(null);

    if (!name.trim()) {
      setError('Informe o nome do evento');
      return;
    }

    if (!startDate || !endDate) {
      setError('Informe data inicial e final');
      return;
    }

    if (selectedProducts.length === 0) {
      setError('Selecione ao menos um produto para o evento');
      return;
    }

    try {
      setSaving(true);
      const isEditing = Boolean(editingEventId);
      const resp = await fetch(isEditing ? `${API_BASE}/events/${editingEventId}` : `${API_BASE}/events`, {
        method: isEditing ? 'PUT' : 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          name: name.trim(),
          start_date: startDate,
          end_date: endDate,
          products: selectedProducts,
        }),
      });

      if (!resp.ok) {
        const errData = await resp.json().catch(() => ({}));
        throw new Error(errData.detail || 'Falha ao criar evento');
      }

      setSuccess(isEditing ? 'Evento atualizado com sucesso' : 'Evento criado com sucesso');
      resetForm();
      await loadEvents();
    } catch (err) {
      setError(err.message);
    } finally {
      setSaving(false);
    }
  }

  return (
    <Layout>
      <div className="page-inner">
        <div className="page-header">
          <div>
            <h2>Cadastro de Eventos</h2>
            <p className="page-subtitle">Crie eventos com período e produtos específicos para análise de vendas</p>
          </div>
        </div>

        {error && <div className="error">{error}</div>}
        {success && <div className="info-box"><p>{success}</p></div>}

        <div className="card" style={{ marginBottom: 20 }}>
          <div className="card-header">
            <h3>{editingEventId ? '✏️ Editar Evento' : '🎪 Novo Evento'}</h3>
          </div>
          <form className="form" onSubmit={handleSubmit}>
            <div className="form-grid">
              <div className="form-group form-group-full">
                <label>Nome do Evento</label>
                <input
                  type="text"
                  placeholder="Ex: Feira de Março"
                  value={name}
                  onChange={(e) => setName(e.target.value)}
                />
              </div>
              <div className="form-group">
                <label>Data Inicial</label>
                <input type="date" value={startDate} onChange={(e) => setStartDate(e.target.value)} />
              </div>
              <div className="form-group">
                <label>Data Final</label>
                <input type="date" value={endDate} onChange={(e) => setEndDate(e.target.value)} />
              </div>
            </div>

            <div className="form-group">
              <label>Produtos do Evento</label>
              <p className="helper-text">Ao selecionar um produto pai, todas as variações filhas são incluídas automaticamente no evento.</p>
              <div className="search-box">
                <input
                  type="text"
                  value={productQuery}
                  onChange={(e) => setProductQuery(e.target.value)}
                  placeholder="Buscar por nome ou SKU"
                />
                <button type="button" className="btn-secondary" onClick={searchProducts} disabled={searchingProducts}>
                  {searchingProducts ? 'Buscando...' : 'Buscar'}
                </button>
              </div>

              {productResults.length > 0 && (
                <div className="search-results">
                  {productResults.map((item) => {
                    const sku = String(item.codigo || '').toUpperCase().trim();
                    const already = selectedSkuSet.has(sku);
                    return (
                      <div className="result-item" key={item.id || sku}>
                        <div>
                          <strong>{item.nome || 'Produto sem nome'}</strong>
                          <p>SKU: {sku || '—'}</p>
                        </div>
                        <button
                          type="button"
                          className="btn-secondary"
                          disabled={already}
                          onClick={() => addProduct(item)}
                        >
                          {already ? 'Selecionado' : 'Adicionar'}
                        </button>
                      </div>
                    );
                  })}
                </div>
              )}

              <div className="chips" style={{ marginTop: 12 }}>
                {selectedProducts.length === 0 && <p>Nenhum produto selecionado.</p>}
                {selectedProducts.map((product) => (
                  <span className="chip" key={product.sku}>
                    {product.sku}
                    <button type="button" onClick={() => removeProduct(product.sku)}>×</button>
                  </span>
                ))}
              </div>
            </div>

            <div style={{ display: 'flex', gap: 10, flexWrap: 'wrap' }}>
              <button type="submit" disabled={saving}>{saving ? 'Salvando...' : (editingEventId ? 'Atualizar Evento' : 'Salvar Evento')}</button>
              {editingEventId && (
                <button type="button" className="btn-secondary" onClick={resetForm}>Cancelar edição</button>
              )}
            </div>
          </form>
        </div>

        <div className="card">
          <div className="card-header">
            <h3>📚 Eventos Cadastrados</h3>
          </div>
          {loadingEvents ? (
            <p className="loading">Carregando eventos...</p>
          ) : events.length === 0 ? (
            <div className="empty-state">
              <span className="empty-state-icon">🗂️</span>
              <p>Nenhum evento cadastrado ainda.</p>
            </div>
          ) : (
            <table className="table">
              <thead>
                <tr>
                  <th>Evento</th>
                  <th>Período</th>
                  <th>Produtos</th>
                  <th>Criado em</th>
                  <th>Ações</th>
                </tr>
              </thead>
              <tbody>
                {events.map((event) => (
                  <tr key={event.id}>
                    <td style={{ fontWeight: 600 }}>{event.name}</td>
                    <td>{formatDate(event.start_date)} até {formatDate(event.end_date)}</td>
                    <td>{event.products_count}</td>
                    <td>{formatDate(event.created_at)}</td>
                    <td style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
                      <button type="button" className="btn-secondary" onClick={() => handleEdit(event.id)}>Editar</button>
                      <button type="button" onClick={() => handleDelete(event.id)}>Excluir</button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>
      </div>
    </Layout>
  );
}
