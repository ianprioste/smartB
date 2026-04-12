import React, { useEffect, useMemo, useState, useCallback, useRef } from 'react';
import { Layout } from '../../components/Layout';
import { ProductionStatusBadge, ProductionNotesInput } from '../../components/ProductionControls';
import useIsMobile from '../../hooks/useIsMobile';
import { useVersionPolling } from '../../hooks/useVersionPolling';

const API_BASE = '/api';

function formatBRL(value) {
  return new Intl.NumberFormat('pt-BR', { style: 'currency', currency: 'BRL' }).format(value ?? 0);
}

function formatDate(value) {
  if (!value) return '—';
  return new Date(value).toLocaleDateString('pt-BR');
}

function StatusBadge({ text }) {
  const lower = (text || '').toLowerCase();
  const cls = lower.includes('atendido') ? 'badge badge--green' : 'badge badge--yellow';
  return <span className={cls}>{text || '—'}</span>;
}

function ChevronIcon({ isExpanded }) {
  return (
    <svg
      width="20"
      height="20"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="2"
      strokeLinecap="round"
      strokeLinejoin="round"
      style={{
        transform: isExpanded ? 'rotate(90deg)' : 'rotate(0deg)',
        transition: 'transform 0.3s cubic-bezier(0.4, 0, 0.2, 1)',
        display: 'inline-block',
      }}
    >
      <polyline points="9 18 15 12 9 6" />
    </svg>
  );
}

function normalizeStatusLabel(value) {
  const lower = (value || '').toString().trim().toLowerCase();
  if (lower.includes('cancel') || lower.includes('devolv')) return 'Cancelado';
  if (lower.includes('atendido') || lower.includes('conclu') || lower.includes('entreg')) return 'Atendido';
  return 'Em aberto';
}

export function EventSalesPage() {
  const isMobile = useIsMobile(768);
  const [events, setEvents] = useState([]);
  const [selectedEventId, setSelectedEventId] = useState('');
  const [salesData, setSalesData] = useState(null);
  const [loadingEvents, setLoadingEvents] = useState(false);
  const [loadingSales, setLoadingSales] = useState(false);
  const [error, setError] = useState(null);
  const [searchTerm, setSearchTerm] = useState('');
  const [selectedStatuses, setSelectedStatuses] = useState(null);
  const [expandedOrderId, setExpandedOrderId] = useState(null);
  const [groupBy, setGroupBy] = useState('pedido');
  const deltaCursorRef = useRef(null);
  const suppressDeltaUntilRef = useRef(0);

  const markLocalMutation = useCallback(() => {
    suppressDeltaUntilRef.current = Date.now() + 4000;
  }, []);

  const handleProductionSaved = useCallback((sku, newStatus, newNotes, orderId) => {
    setSalesData((prev) => {
      if (!prev) return prev;
      const orders = prev.orders.map((order) => {
        // When orderId is provided, only update the matching order's item
        if (orderId && order.id !== orderId) return order;
        const items = order.matched_items.map((item) => {
          if ((item.sku || '').toUpperCase() !== (sku || '').toUpperCase()) return item;
          return {
            ...item,
            ...(newStatus !== undefined ? { production_status: newStatus } : {}),
            ...(newNotes !== undefined ? { notes: newNotes } : {}),
          };
        });
        const embalado = items.filter((i) => i.production_status === 'Embalado').length;
        return { ...order, matched_items: items, production_summary: `${embalado}/${items.length} Embalado` };
      });
      return { ...prev, orders };
    });
  }, []);

  const handleProductionStatusChange = useCallback(async (sku, orderId, currentStatus, nextStatus) => {
    if (nextStatus === currentStatus) return;
    try {
      await fetch(`${API_BASE}/events/${selectedEventId}/items/${encodeURIComponent(sku)}/production`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ production_status: nextStatus, bling_order_id: orderId || null }),
      });
      markLocalMutation();
      handleProductionSaved(sku, nextStatus, undefined, orderId);
    } catch (err) {
      console.error('Failed to save production status', err);
    }
  }, [selectedEventId, handleProductionSaved, markLocalMutation]);

  const handleProductionNotesChange = useCallback((sku, orderId, productionStatus, notes) => {
    fetch(`${API_BASE}/events/${selectedEventId}/items/${encodeURIComponent(sku)}/production`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ production_status: productionStatus || 'Pendente', notes, bling_order_id: orderId || null }),
    }).catch(() => {});
    markLocalMutation();
    handleProductionSaved(sku, undefined, notes, orderId);
  }, [selectedEventId, handleProductionSaved, markLocalMutation]);

  const handleOrderStatusChange = useCallback(async (orderId, newStatus) => {
    try {
      const resp = await fetch(`${API_BASE}/events/${selectedEventId}/orders/${orderId}/status`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ situacao: newStatus }),
      });
      if (!resp.ok) throw new Error('Falha ao atualizar status');
      markLocalMutation();
      setSalesData((prev) => {
        if (!prev) return prev;
        const orders = prev.orders.map((o) => o.id === orderId ? { ...o, situacao: newStatus } : o);
        return { ...prev, orders };
      });
    } catch (err) {
      alert(`Erro: ${err.message}`);
    }
  }, [markLocalMutation, selectedEventId]);

  async function loadEvents() {
    try {
      setLoadingEvents(true);
      const resp = await fetch(`${API_BASE}/events`);
      if (!resp.ok) throw new Error('Falha ao carregar campanhas');
      const data = await resp.json();
      const list = Array.isArray(data) ? data : [];
      setEvents(list);
      if (!selectedEventId && list.length > 0) {
        setSelectedEventId(list[0].id);
      }
    } catch (err) {
      setError(err.message);
    } finally {
      setLoadingEvents(false);
    }
  }

  const loadSales = useCallback(async (eventId) => {
    if (!eventId) {
      setSalesData(null);
      return;
    }

    try {
      setLoadingSales(true);
      setError(null);
      const resp = await fetch(`${API_BASE}/events/${eventId}/sales`);
      if (!resp.ok) {
        const errData = await resp.json().catch(() => ({}));
        throw new Error(errData.detail || 'Falha ao carregar vendas da campanha');
      }
      setSalesData(await resp.json());
      deltaCursorRef.current = new Date().toISOString();
    } catch (err) {
      setError(err.message);
      setSalesData(null);
    } finally {
      setLoadingSales(false);
    }
  }, []);

  const fetchEventVersion = useCallback(async () => {
    if (!selectedEventId) return null;
    const resp = await fetch(`${API_BASE}/events/${selectedEventId}/sync/version`);
    if (!resp.ok) return null;
    const data = await resp.json();
    if (data.last_updated_at) {
      deltaCursorRef.current = data.last_updated_at;
    }
    return data.current_version;
  }, [selectedEventId]);

  const handleEventVersionChange = useCallback(async () => {
    if (Date.now() < suppressDeltaUntilRef.current) {
      return;
    }
    if (!selectedEventId) return;
    try {
      const params = new URLSearchParams();
      if (deltaCursorRef.current) {
        params.set('since', deltaCursorRef.current);
      }
      const resp = await fetch(`${API_BASE}/events/${selectedEventId}/sync/updates?${params.toString()}`);
      if (!resp.ok) {
        return;
      }
      const delta = await resp.json();
      if (delta.server_time) {
        deltaCursorRef.current = delta.server_time;
      }

      const statusMap = new Map((delta.order_status_updates || []).map((u) => [Number(u.order_id), u.situacao]));
      const productionUpdates = delta.production_updates || [];

      setSalesData((prev) => {
        if (!prev) return prev;
        const orders = (prev.orders || []).map((order) => {
          const orderId = Number(order.id);
          const nextStatus = statusMap.get(orderId);
          const matchedItems = (order.matched_items || []).map((item) => {
            const sku = (item.sku || '').toUpperCase();
            const match = productionUpdates.find((u) => {
              if ((u.sku || '').toUpperCase() !== sku) return false;
              if (u.bling_order_id == null) return true;
              return Number(u.bling_order_id) === orderId;
            });
            if (!match) return item;
            return {
              ...item,
              production_status: match.production_status,
              notes: match.notes,
            };
          });
          const embalado = matchedItems.filter((i) => i.production_status === 'Embalado').length;
          return {
            ...order,
            ...(nextStatus ? { situacao: nextStatus } : {}),
            matched_items: matchedItems,
            production_summary: `${embalado}/${matchedItems.length} Embalado`,
          };
        });
        return { ...prev, orders };
      });
    } catch {
      // Keep current list stable; retry on next polling cycle.
    }
  }, [selectedEventId]);

  useEffect(() => {
    loadEvents();
  }, []);

  useEffect(() => {
    if (selectedEventId) {
      setSelectedStatuses(null);
      loadSales(selectedEventId);
    }
  }, [loadSales, selectedEventId]);

  useVersionPolling({
    enabled: Boolean(selectedEventId) && !loadingSales,
    pollKey: selectedEventId ? `event_sales:${selectedEventId}` : 'event_sales:none',
    fetchVersion: fetchEventVersion,
    onVersionChange: handleEventVersionChange,
    intervalMsActive: 7000,
    intervalMsHidden: 15000,
  });

  const availableStatuses = useMemo(() => {
    const allOrders = Array.isArray(salesData?.orders) ? salesData.orders : [];
    const statusSet = new Set();
    allOrders.forEach((order) => statusSet.add(normalizeStatusLabel(order.situacao)));
    return [...statusSet].sort();
  }, [salesData]);

  useEffect(() => {
    if (availableStatuses.length > 0) {
      setSelectedStatuses((prev) => {
        if (prev === null) return new Set(availableStatuses);
        return prev;
      });
    }
  }, [availableStatuses]);

  const visibleOrders = useMemo(() => {
    const allOrders = Array.isArray(salesData?.orders) ? salesData.orders : [];
    const term = (searchTerm || '').trim().toLowerCase();
    const activeStatuses = selectedStatuses || new Set();

    return allOrders.filter((order) => {
      const statusLabel = normalizeStatusLabel(order.situacao);
      const statusOk = activeStatuses.has(statusLabel);
      if (!statusOk) return false;

      if (!term) return true;

      const pedidoText = String(order.numero || order.id || '').toLowerCase();
      const clienteText = String(order.cliente || '').toLowerCase();
      return pedidoText.includes(term) || clienteText.includes(term);
    });
  }, [salesData, searchTerm, selectedStatuses]);

  const filteredSummary = useMemo(() => {
    const matchedItemsCount = visibleOrders.reduce((acc, order) => acc + (order.matched_items?.length || 0), 0);
    const totalMatched = visibleOrders.reduce((acc, order) => acc + (order.total_matched || 0), 0);
    return {
      orders_count: visibleOrders.length,
      matched_items_count: matchedItemsCount,
      total_matched: totalMatched,
    };
  }, [visibleOrders]);

  const toggleStatus = (label) => {
    setSelectedStatuses((prev) => {
      const next = new Set(prev);
      if (next.has(label)) next.delete(label);
      else next.add(label);
      return next;
    });
  };

  const toggleOrder = (orderId) => {
    setExpandedOrderId((prev) => (prev === orderId ? null : orderId));
  };

  const groupedByItem = useMemo(() => {
    if (groupBy !== 'item') return [];

    const SIZE_ORDER = ['PP', 'P', 'M', 'G', 'GG', 'XG', 'EXG', 'XXL', '6', '8', '10', '12', '14', '16'];

    function extractModelAndSize(sku, productName) {
      const raw = (sku || '').toUpperCase();
      // Try hyphenated SKU: last segment is size (e.g. BL-DTQD-BR-GG)
      const hyphenParts = raw.split('-');
      if (hyphenParts.length >= 2) {
        const lastPart = hyphenParts[hyphenParts.length - 1];
        if (SIZE_ORDER.includes(lastPart)) {
          return { model: hyphenParts.slice(0, -1).join('-'), size: lastPart };
        }
      }
      // Try compact SKU: ends with size token (e.g. BLDTQDBRGG)
      for (let i = SIZE_ORDER.length - 1; i >= 0; i--) {
        if (raw.endsWith(SIZE_ORDER[i]) && raw.length > SIZE_ORDER[i].length) {
          return { model: raw.slice(0, -SIZE_ORDER[i].length), size: SIZE_ORDER[i] };
        }
      }
      // Try product_name: size often in parentheses
      const nameMatch = (productName || '').match(/\b(PP|EXG|XXL|XG|GG|G|M|P)\b/i);
      if (nameMatch) {
        const size = nameMatch[1].toUpperCase();
        return { model: (productName || '').replace(/\s*\(.*$/, '').trim(), size };
      }
      return { model: raw || (productName || '').trim(), size: '' };
    }

    const itemMap = {};
    visibleOrders.forEach((order) => {
      const items = Array.isArray(order.matched_items) ? order.matched_items : [];
      items.forEach((item) => {
        const key = item.sku || item.product_name;
        if (!itemMap[key]) {
          const { model, size } = extractModelAndSize(item.sku, item.product_name);
          itemMap[key] = {
            sku: item.sku, product_name: item.product_name, total_qty: 0, total_paid: 0, orders: [],
            _model: model, _size: size,
            production_status: item.production_status || 'Pendente',
            notes: item.notes || '',
          };
        }
        itemMap[key].total_qty += (item.quantity || 0);
        itemMap[key].total_paid += (item.paid_total || 0);
        itemMap[key].orders.push({
          order_id: order.id,
          numero: order.numero || order.id,
          numero_loja: order.numero_loja,
          data: order.data,
          cliente: order.cliente,
          situacao: order.situacao,
          quantity: item.quantity,
          paid_unit_price: item.paid_unit_price,
          paid_total: item.paid_total,
          production_status: item.production_status || 'Pendente',
          notes: item.notes || '',
        });
      });
    });

    return Object.values(itemMap).sort((a, b) => {
      if (a._model < b._model) return -1;
      if (a._model > b._model) return 1;
      const ai = SIZE_ORDER.indexOf(a._size);
      const bi = SIZE_ORDER.indexOf(b._size);
      return (ai === -1 ? 999 : ai) - (bi === -1 ? 999 : bi);
    });
  }, [visibleOrders, groupBy]);

  return (
    <Layout>
      <div className="page-inner">
        <div className="page-header">
          <div>
            <h2>Vendas por Campanha</h2>
            <p className="page-subtitle">Pedidos de venda filtrados pelos produtos selecionados na campanha</p>
          </div>
          <button className="btn-secondary" disabled={!selectedEventId || loadingSales} onClick={() => loadSales(selectedEventId)}>
            {loadingSales ? 'Atualizando...' : 'Atualizar'}
          </button>
        </div>

        {error && <div className="error">{error}</div>}

        <div className="card" style={{ marginBottom: 16 }}>
          <div className="card-header">
            <h3>📌 Seleção de Campanha</h3>
          </div>
          <div style={{ padding: 20 }}>
            {loadingEvents ? (
              <p className="loading">Carregando campanhas...</p>
            ) : (
              <div className="form-group" style={{ marginBottom: 0 }}>
                <label>Campanha</label>
                <select value={selectedEventId} onChange={(e) => setSelectedEventId(e.target.value)}>
                  <option value="">Selecione uma campanha</option>
                  {events.map((event) => (
                    <option value={event.id} key={event.id}>
                      {event.name} ({formatDate(event.start_date)} - {formatDate(event.end_date)})
                    </option>
                  ))}
                </select>
              </div>
            )}
          </div>
        </div>

        {salesData && (
          <>
            <div className="card" style={{ marginBottom: 16 }}>
              <div style={{ padding: '16px 20px' }}>
                <div className="search-box" style={{ marginBottom: 12 }}>
                  <input
                    type="text"
                    placeholder="Buscar por nº do pedido ou nome do cliente..."
                    value={searchTerm}
                    onChange={(e) => setSearchTerm(e.target.value)}
                  />
                </div>
                <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap', alignItems: 'center' }}>
                  <span style={{ fontSize: 13, color: '#64748b', marginRight: 4 }}>Status:</span>
                  {availableStatuses.map((statusLabel) => {
                    const active = selectedStatuses?.has(statusLabel);
                    return (
                      <button
                        key={statusLabel}
                        onClick={() => toggleStatus(statusLabel)}
                        style={{
                          cursor: 'pointer',
                          border: active ? '2px solid #3b82f6' : '2px solid transparent',
                          padding: '5px 12px',
                          borderRadius: 16,
                          fontSize: 13,
                          fontWeight: active ? 600 : 400,
                          background: active ? '#dbeafe' : '#f1f5f9',
                          color: active ? '#1d4ed8' : '#475569',
                          transition: 'all 0.15s ease',
                        }}
                      >
                        {statusLabel}
                      </button>
                    );
                  })}
                </div>
              </div>
            </div>

            <div className="stats-grid" style={{ marginBottom: 16 }}>
              <div className="stat-card stat-card--blue">
                <div className="stat-body">
                  <div className="stat-value">{filteredSummary.orders_count}</div>
                  <div className="stat-label">Pedidos com Itens do Evento</div>
                </div>
              </div>
              <div className="stat-card stat-card--green">
                <div className="stat-body">
                  <div className="stat-value">{filteredSummary.matched_items_count}</div>
                  <div className="stat-label">Itens Relacionados</div>
                </div>
              </div>
              <div className="stat-card stat-card--yellow">
                <div className="stat-body">
                  <div className="stat-value">{formatBRL(filteredSummary.total_matched)}</div>
                  <div className="stat-label">Total dos Itens do Evento</div>
                </div>
              </div>
            </div>

            <div className="card">
              <div className="card-header" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: 8 }}>
                <h3>📋 Pedidos Filtrados</h3>
                <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                  <span style={{ fontSize: 12, color: '#94a3b8' }}>Agrupar:</span>
                  {[{ key: 'pedido', label: 'Por Pedido' }, { key: 'item', label: 'Por Item' }].map((opt) => (
                    <button
                      key={opt.key}
                      onClick={() => { setGroupBy(opt.key); setExpandedOrderId(null); }}
                      style={{
                        cursor: 'pointer',
                        border: groupBy === opt.key ? '2px solid #3b82f6' : '2px solid transparent',
                        padding: '4px 12px',
                        borderRadius: 16,
                        fontSize: 12,
                        fontWeight: groupBy === opt.key ? 600 : 400,
                        background: groupBy === opt.key ? '#dbeafe' : '#f1f5f9',
                        color: groupBy === opt.key ? '#1d4ed8' : '#475569',
                        transition: 'all 0.15s ease',
                      }}
                    >
                      {opt.label}
                    </button>
                  ))}
                  {!loadingSales && <span style={{ fontSize: 13, color: '#94a3b8' }}>{filteredSummary.orders_count} pedido(s)</span>}
                </div>
              </div>
              {loadingSales ? (
                <p className="loading">Carregando vendas...</p>
              ) : (
                groupBy === 'item' ? (
                  groupedByItem.length === 0 ? (
                    <div className="empty-state">
                      <span className="empty-state-icon">📭</span>
                      <p>Nenhum item encontrado.</p>
                    </div>
                  ) : isMobile ? (
                    <div style={{ display: 'grid', gap: 12, padding: 12 }}>
                      {groupedByItem.map((group) => {
                        const gKey = group.sku || group.product_name;
                        const isExpanded = expandedOrderId === gKey;
                        return (
                          <div key={gKey} style={{ border: '1px solid #e2e8f0', borderRadius: 10, overflow: 'hidden', background: '#fff' }}>
                            <button
                              onClick={() => toggleOrder(gKey)}
                              style={{ width: '100%', border: 'none', textAlign: 'left', background: isExpanded ? '#f0f9ff' : '#fff', padding: 14, cursor: 'pointer' }}
                            >
                              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: 8, marginBottom: 8 }}>
                                <div style={{ fontWeight: 700, color: '#1e293b' }}>{group.sku || '—'}</div>
                                <ChevronIcon isExpanded={isExpanded} />
                              </div>
                              <div style={{ fontSize: 13, fontWeight: 600, color: '#334155', marginBottom: 8 }}>{group.product_name}</div>
                              <div style={{ display: 'flex', flexWrap: 'wrap', gap: 10, fontSize: 12, color: '#64748b' }}>
                                <span><strong>Qtd:</strong> {group.total_qty}</span>
                                <span><strong>Total:</strong> {formatBRL(group.total_paid)}</span>
                                <span><strong>Pedidos:</strong> {group.orders.length}</span>
                              </div>
                            </button>

                            {isExpanded && (
                              <div style={{ borderTop: '1px solid #e2e8f0', background: '#f8fafc', padding: 12, display: 'grid', gap: 10 }}>
                                {group.orders.map((o, idx) => (
                                  <div key={`${gKey}-${o.numero}-${idx}`} style={{ border: '1px solid #e2e8f0', borderRadius: 8, background: '#fff', padding: 10 }}>
                                    <div style={{ display: 'flex', justifyContent: 'space-between', gap: 8, marginBottom: 8 }}>
                                      <div style={{ fontWeight: 700, color: '#1e293b' }}>Pedido {o.numero}</div>
                                      <div style={{ fontWeight: 700, color: '#1e293b' }}>{formatBRL(o.paid_total)}</div>
                                    </div>
                                    <div style={{ fontSize: 12, color: '#64748b', marginBottom: 6 }}><strong>Cliente:</strong> {o.cliente || '—'}</div>
                                    <div style={{ fontSize: 12, color: '#64748b', marginBottom: 6 }}><strong>Nuvemshop:</strong> {o.numero_loja || '—'}</div>
                                    <div style={{ fontSize: 12, color: '#64748b', marginBottom: 8 }}><strong>Data:</strong> {formatDate(o.data)}</div>
                                    <div style={{ marginBottom: 8 }}><StatusBadge text={o.situacao} /></div>
                                    <div style={{ display: 'flex', justifyContent: 'space-between', gap: 8, fontSize: 12, color: '#64748b', marginBottom: 8 }}>
                                      <span><strong>Qtd:</strong> {o.quantity}</span>
                                    </div>
                                    <div style={{ marginBottom: 8 }}>
                                      <ProductionStatusBadge
                                        status={o.production_status}
                                        onChangeStatus={(nextStatus) => handleProductionStatusChange(group.sku, o.order_id, o.production_status, nextStatus)}
                                      />
                                    </div>
                                    <ProductionNotesInput
                                      initialValue={o.notes}
                                      status={o.production_status}
                                      onChangeNotes={(notes) => handleProductionNotesChange(group.sku, o.order_id, o.production_status, notes)}
                                    />
                                  </div>
                                ))}
                              </div>
                            )}
                          </div>
                        );
                      })}
                    </div>
                  ) : (
                    <table className="table">
                      <thead>
                        <tr>
                          <th style={{ width: 40 }}></th>
                          <th>SKU</th>
                          <th>Produto</th>
                          <th style={{ textAlign: 'right' }}>Qtd Total</th>
                          <th style={{ textAlign: 'right' }}>Total Pago</th>
                          <th style={{ textAlign: 'right' }}>Pedidos</th>
                        </tr>
                      </thead>
                      <tbody>
                        {groupedByItem.map((group) => {
                          const gKey = group.sku || group.product_name;
                          const isExpanded = expandedOrderId === gKey;
                          return (
                            <React.Fragment key={gKey}>
                              <tr
                                style={{ cursor: 'pointer', background: isExpanded ? '#f0f9ff' : undefined }}
                                onClick={() => toggleOrder(gKey)}
                              >
                                <td style={{ textAlign: 'center', color: '#64748b', paddingTop: 12, paddingBottom: 12 }}>
                                  <ChevronIcon isExpanded={isExpanded} />
                                </td>
                                <td style={{ fontFamily: 'monospace', color: '#64748b' }}>{group.sku || '—'}</td>
                                <td style={{ fontWeight: 600 }}>{group.product_name}</td>
                                <td style={{ textAlign: 'right', fontWeight: 600 }}>{group.total_qty}</td>
                                <td style={{ textAlign: 'right', fontWeight: 600 }}>{formatBRL(group.total_paid)}</td>
                                <td style={{ textAlign: 'right', color: '#64748b' }}>{group.orders.length}</td>
                              </tr>
                              {isExpanded && (
                                <tr style={{ background: '#f8fafc', borderTop: '2px solid #e2e8f0' }}>
                                  <td colSpan="6" style={{ padding: '16px 20px' }}>
                                    <h4 style={{ margin: '0 0 12px 0', color: '#1e293b', fontSize: 14 }}>📦 Pedidos com este item</h4>
                                    <table style={{ width: '100%', fontSize: 13, borderCollapse: 'collapse' }}>
                                      <thead>
                                        <tr style={{ borderBottom: '1px solid #cbd5e1' }}>
                                          <th style={{ textAlign: 'left', padding: '8px', fontWeight: 600, color: '#475569' }}>Pedido</th>
                                          <th style={{ textAlign: 'left', padding: '8px', fontWeight: 600, color: '#475569' }}>Nuvemshop</th>
                                          <th style={{ textAlign: 'left', padding: '8px', fontWeight: 600, color: '#475569' }}>Data</th>
                                          <th style={{ textAlign: 'left', padding: '8px', fontWeight: 600, color: '#475569' }}>Cliente</th>
                                          <th style={{ textAlign: 'left', padding: '8px', fontWeight: 600, color: '#475569' }}>Situação</th>
                                          <th style={{ textAlign: 'left', padding: '8px', fontWeight: 600, color: '#475569' }}>Produção</th>
                                          <th style={{ textAlign: 'right', padding: '8px', fontWeight: 600, color: '#475569', width: 80 }}>Qtd</th>
                                          <th style={{ textAlign: 'right', padding: '8px', fontWeight: 600, color: '#475569', width: 100 }}>Total Pago</th>
                                          <th style={{ textAlign: 'left', padding: '8px', fontWeight: 600, color: '#475569' }}>Notas</th>
                                        </tr>
                                      </thead>
                                      <tbody>
                                        {group.orders.map((o, idx) => (
                                          <tr key={`${gKey}-${o.numero}-${idx}`} style={{ borderBottom: '1px solid #f1f5f9' }}>
                                            <td style={{ padding: '8px', fontWeight: 600 }}>{o.numero}</td>
                                            <td style={{ padding: '8px', color: '#64748b' }}>{o.numero_loja || '—'}</td>
                                            <td style={{ padding: '8px', color: '#64748b' }}>{formatDate(o.data)}</td>
                                            <td style={{ padding: '8px', color: '#334155' }}>{o.cliente || '—'}</td>
                                            <td style={{ padding: '8px' }}><StatusBadge text={o.situacao} /></td>
                                            <td style={{ padding: '8px' }}>
                                              <ProductionStatusBadge
                                                status={o.production_status}
                                                onChangeStatus={(nextStatus) => handleProductionStatusChange(group.sku, o.order_id, o.production_status, nextStatus)}
                                              />
                                            </td>
                                            <td style={{ textAlign: 'right', padding: '8px', color: '#64748b' }}>{o.quantity}</td>
                                            <td style={{ textAlign: 'right', padding: '8px', fontWeight: 600, color: '#1e293b' }}>{formatBRL(o.paid_total)}</td>
                                            <td style={{ padding: '8px', minWidth: 150 }}>
                                              <ProductionNotesInput
                                                initialValue={o.notes}
                                                status={o.production_status}
                                                onChangeNotes={(notes) => handleProductionNotesChange(group.sku, o.order_id, o.production_status, notes)}
                                              />
                                            </td>
                                          </tr>
                                        ))}
                                      </tbody>
                                    </table>
                              </td>
                                </tr>
                              )}
                            </React.Fragment>
                          );
                        })}
                      </tbody>
                    </table>
                  )
                ) : visibleOrders.length === 0 ? (
                <div className="empty-state">
                  <span className="empty-state-icon">📭</span>
                  <p>Nenhuma venda encontrada para os produtos deste evento no período selecionado.</p>
                </div>
              ) : isMobile ? (
                <div style={{ display: 'grid', gap: 12, padding: 12 }}>
                  {visibleOrders.map((order) => {
                    const orderKey = order.id || order.numero;
                    const isExpanded = expandedOrderId === orderKey;
                    const matchedItems = Array.isArray(order.matched_items) ? order.matched_items : [];
                    const allEmbalado = matchedItems.length > 0 && matchedItems.every((i) => i.production_status === 'Embalado');

                    return (
                      <div key={orderKey} style={{ border: '1px solid #e2e8f0', borderRadius: 10, overflow: 'hidden', background: '#fff' }}>
                        <button
                          onClick={() => toggleOrder(orderKey)}
                          style={{ width: '100%', border: 'none', textAlign: 'left', background: isExpanded ? '#f0f9ff' : '#fff', padding: 14, cursor: 'pointer' }}
                        >
                          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: 8, marginBottom: 8 }}>
                            <div style={{ fontWeight: 700, color: '#1e293b' }}>Pedido {order.numero || order.id} • {order.cliente || '—'}</div>
                            <div style={{ fontWeight: 700, color: '#1e293b' }}>{formatBRL(order.total_matched)}</div>
                          </div>
                          <div style={{ fontSize: 12, color: '#64748b', marginBottom: 6 }}><strong>Data:</strong> {formatDate(order.data)}</div>
                          <div style={{ fontSize: 12, color: '#475569', marginBottom: 8 }}><strong>Código:</strong> {order.numero_loja || '—'}</div>
                          <div style={{ display: 'flex', alignItems: 'center', gap: 8, flexWrap: 'wrap' }}>
                            <StatusBadge text={order.situacao} />
                            <span style={{ fontSize: 12, color: '#64748b' }}>{order.production_summary || '—'}</span>
                            <span title={order.has_frete ? 'Envio' : 'Retirada'}>{order.has_frete ? '🚚' : '🏪'}</span>
                            {matchedItems.length > 0 && <ChevronIcon isExpanded={isExpanded} />}
                          </div>
                        </button>

                        {isExpanded && matchedItems.length > 0 && (
                          <div style={{ borderTop: '1px solid #e2e8f0', background: '#f8fafc', padding: 12 }}>
                            {allEmbalado && order.situacao !== 'Atendido' && (
                              <div style={{ marginBottom: 12 }}>
                                <button
                                  className="btn-secondary"
                                  style={{ fontSize: 12, padding: '4px 12px' }}
                                  onClick={(e) => { e.stopPropagation(); handleOrderStatusChange(order.id, 'Atendido'); }}
                                >
                                  ✅ Marcar como Atendido
                                </button>
                              </div>
                            )}

                            <div style={{ display: 'grid', gap: 10 }}>
                              {matchedItems.map((item) => (
                                <div key={`${orderKey}-${item.sku}`} style={{ border: '1px solid #e2e8f0', borderRadius: 8, background: '#fff', padding: 10 }}>
                                  <div style={{ fontSize: 12, color: '#64748b', fontFamily: 'monospace', marginBottom: 4 }}>{item.sku || '—'}</div>
                                  <div style={{ fontSize: 13, fontWeight: 600, color: '#334155', marginBottom: 8 }}>{item.product_name}</div>
                                  <div style={{ display: 'flex', justifyContent: 'space-between', gap: 8, fontSize: 12, color: '#64748b', marginBottom: 8 }}>
                                    <span><strong>Qtd:</strong> {item.quantity}</span>
                                    <span><strong>Total:</strong> {formatBRL(item.paid_total)}</span>
                                  </div>
                                  <div style={{ marginBottom: 8 }}>
                                    <ProductionStatusBadge
                                      status={item.production_status}
                                      onChangeStatus={(nextStatus) => handleProductionStatusChange(item.sku, order.id, item.production_status, nextStatus)}
                                    />
                                  </div>
                                  <ProductionNotesInput
                                    initialValue={item.notes}
                                    status={item.production_status}
                                    onChangeNotes={(notes) => handleProductionNotesChange(item.sku, order.id, item.production_status, notes)}
                                  />
                                </div>
                              ))}
                            </div>
                          </div>
                        )}
                      </div>
                    );
                  })}
                </div>
              ) : (
                <table className="table">
                  <thead>
                    <tr>
                      <th style={{ width: 40 }}></th>
                      <th>Pedido</th>
                      <th>Nuvemshop</th>
                      <th>Data</th>
                      <th>Cliente</th>
                      <th>Situação</th>
                      <th>Produção</th>
                      <th></th>
                      <th>Total Itens Evento</th>
                    </tr>
                  </thead>
                  <tbody>
                    {visibleOrders.map((order) => {
                      const orderKey = order.id || order.numero;
                      const isExpanded = expandedOrderId === orderKey;
                      const matchedItems = Array.isArray(order.matched_items) ? order.matched_items : [];
                      const allEmbalado = matchedItems.length > 0 && matchedItems.every((i) => i.production_status === 'Embalado');

                      return (
                        <React.Fragment key={orderKey}>
                          <tr
                            style={{ cursor: 'pointer', background: isExpanded ? '#f0f9ff' : undefined }}
                            onClick={() => toggleOrder(orderKey)}
                          >
                            <td style={{ textAlign: 'center', color: '#64748b', paddingTop: 12, paddingBottom: 12 }}>
                              {matchedItems.length > 0 && <ChevronIcon isExpanded={isExpanded} />}
                            </td>
                            <td style={{ fontWeight: 600 }}>{order.numero || order.id}</td>
                            <td style={{ color: '#64748b' }}>{order.numero_loja || '—'}</td>
                            <td>{formatDate(order.data)}</td>
                            <td>{order.cliente || '—'}</td>
                            <td><StatusBadge text={order.situacao} /></td>
                            <td style={{ fontSize: 12, color: '#64748b' }}>{order.production_summary || '—'}</td>
                            <td style={{ fontSize: 14 }} title={order.has_frete ? 'Envio' : 'Retirada'}>{order.has_frete ? '🚚' : '🏪'}</td>
                            <td style={{ fontWeight: 600 }}>{formatBRL(order.total_matched)}</td>
                          </tr>

                          {isExpanded && matchedItems.length > 0 && (
                            <tr style={{ background: '#f8fafc', borderTop: '2px solid #e2e8f0' }}>
                              <td colSpan="9" style={{ padding: '16px 20px' }}>
                                {allEmbalado && order.situacao !== 'Atendido' && (
                                  <div style={{ marginBottom: 12, display: 'flex', gap: 8 }}>
                                    <button
                                      className="btn-secondary"
                                      style={{ fontSize: 12, padding: '4px 12px' }}
                                      onClick={(e) => { e.stopPropagation(); handleOrderStatusChange(order.id, 'Atendido'); }}
                                    >
                                      ✅ Marcar como Atendido
                                    </button>
                                  </div>
                                )}
                                <div style={{ marginBottom: 12 }}>
                                  <h4 style={{ margin: '0 0 12px 0', color: '#1e293b', fontSize: 14 }}>📦 Itens do Evento no Pedido</h4>
                                  <table style={{ width: '100%', fontSize: 13, borderCollapse: 'collapse' }}>
                                    <thead>
                                      <tr style={{ borderBottom: '1px solid #cbd5e1' }}>
                                        <th style={{ textAlign: 'left', padding: '8px', fontWeight: 600, color: '#475569' }}>SKU</th>
                                        <th style={{ textAlign: 'left', padding: '8px', fontWeight: 600, color: '#475569' }}>Produto</th>
                                        <th style={{ textAlign: 'left', padding: '8px', fontWeight: 600, color: '#475569' }}>Produção</th>
                                        <th style={{ textAlign: 'right', padding: '8px', fontWeight: 600, color: '#475569', width: 80 }}>Qtd</th>
                                        <th style={{ textAlign: 'right', padding: '8px', fontWeight: 600, color: '#475569', width: 100 }}>Total Pago</th>
                                        <th style={{ textAlign: 'left', padding: '8px', fontWeight: 600, color: '#475569' }}>Notas</th>
                                      </tr>
                                    </thead>
                                    <tbody>
                                      {matchedItems.map((item) => (
                                        <tr key={`${orderKey}-${item.sku}`} style={{ borderBottom: '1px solid #f1f5f9' }}>
                                          <td style={{ padding: '8px', color: '#64748b', fontFamily: 'monospace' }}>{item.sku || '—'}</td>
                                          <td style={{ padding: '8px', color: '#334155' }}>{item.product_name}</td>
                                          <td style={{ padding: '8px' }}>
                                            <ProductionStatusBadge
                                              status={item.production_status}
                                              onChangeStatus={(nextStatus) => handleProductionStatusChange(item.sku, order.id, item.production_status, nextStatus)}
                                            />
                                          </td>
                                          <td style={{ textAlign: 'right', padding: '8px', color: '#64748b' }}>{item.quantity}</td>
                                          <td style={{ textAlign: 'right', padding: '8px', fontWeight: 600, color: '#1e293b' }}>{formatBRL(item.paid_total)}</td>
                                          <td style={{ padding: '8px', minWidth: 150 }}>
                                            <ProductionNotesInput
                                              initialValue={item.notes}
                                              status={item.production_status}
                                              onChangeNotes={(notes) => handleProductionNotesChange(item.sku, order.id, item.production_status, notes)}
                                            />
                                          </td>
                                        </tr>
                                      ))}
                                    </tbody>
                                  </table>
                                </div>
                              </td>
                            </tr>
                          )}
                        </React.Fragment>
                      );
                    })}
                  </tbody>
                </table>
              )
              )}
            </div>
          </>
        )}
      </div>
    </Layout>
  );
}
