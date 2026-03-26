import React, { useEffect, useState, useCallback, useRef } from 'react';
import { Layout } from '../../components/Layout';

const API_BASE = '/api';

const KNOWN_STATUSES = [
  { id: 6, nome: 'Em aberto' },
  { id: 9, nome: 'Atendido' },
  { id: 15, nome: 'Cancelado' },
];

const DEFAULT_STATUS_IDS = [6, 9, 15];

function formatBRL(value) {
  return new Intl.NumberFormat('pt-BR', { style: 'currency', currency: 'BRL' }).format(value ?? 0);
}

function formatDateTime(value) {
  if (!value) return '—';
  const dt = new Date(value);
  if (Number.isNaN(dt.getTime())) return '—';
  return dt.toLocaleString('pt-BR');
}

function StatusBadge({ text }) {
  const lower = (text || '').toLowerCase();
  let cls = 'badge badge--gray';
  if (lower.includes('atendido') || lower.includes('conclu') || lower.includes('entregue')) cls = 'badge badge--green';
  else if (lower.includes('pendente') || lower.includes('aberto') || lower.includes('andamento')) cls = 'badge badge--yellow';
  else if (lower.includes('cancel') || lower.includes('devolvido')) cls = 'badge badge--red';
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

export function OrdersPage() {
  const [orders, setOrders] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [hasBling, setHasBling] = useState(false);
  const [syncStatus, setSyncStatus] = useState(null);
  const [syncLoading, setSyncLoading] = useState(false);
  const [syncRunning, setSyncRunning] = useState(false);
  const [sourceMode, setSourceMode] = useState('');
  const [search, setSearch] = useState('');
  const [selectedStatuses, setSelectedStatuses] = useState(() => new Set(DEFAULT_STATUS_IDS));
  const [page, setPage] = useState(1);
  const [totalPages, setTotalPages] = useState(0);
  const [total, setTotal] = useState(0);
  const [syncMessage, setSyncMessage] = useState('');
  const [expandedOrderId, setExpandedOrderId] = useState(null);
  const debounceRef = useRef(null);
  const pollRef = useRef(null);
  const prevSyncStatusRef = useRef(null);
  const pollAttemptsRef = useRef(0);

  const fetchOrders = useCallback(async (searchTerm, statuses, pageNum) => {
    try {
      setLoading(true);
      setError(null);
      const statusStr = Array.from(statuses).join(',');
      const params = new URLSearchParams({
        page: String(pageNum),
        limit: '50',
        statuses: statusStr,
      });
      if (searchTerm) params.set('search', searchTerm);

      const resp = await fetch(`${API_BASE}/orders?${params}`);
      if (!resp.ok) throw new Error('Falha ao carregar pedidos');
      const data = await resp.json();

      setHasBling(data.has_bling_auth);
      setSourceMode(data.source || '');
      setOrders(data.data ?? []);
      setTotal(data.total ?? 0);
      setTotalPages(data.pages ?? 0);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }, []);

  const fetchSyncStatus = useCallback(async () => {
    try {
      setSyncLoading(true);
      const resp = await fetch(`${API_BASE}/orders/sync/status`);
      if (!resp.ok) return;
      const data = await resp.json();
      setSyncStatus(data);
    } catch {
      // silently ignore
    } finally {
      setSyncLoading(false);
    }
  }, []);

  const stopPolling = useCallback(() => {
    if (pollRef.current) {
      clearInterval(pollRef.current);
      pollRef.current = null;
    }
    pollAttemptsRef.current = 0;
  }, []);

  const startPolling = useCallback(() => {
    stopPolling();
    pollAttemptsRef.current = 0;
    pollRef.current = setInterval(() => {
      fetch(`${API_BASE}/orders/sync/status`)
        .then((r) => r.json())
        .then((data) => {
          pollAttemptsRef.current += 1;
          const prevStatus = prevSyncStatusRef.current;
          const status = data?.sync?.last_sync_status;
          prevSyncStatusRef.current = status;
          setSyncStatus(data);

          if (status === 'ok' && prevStatus !== 'ok') {
            setSyncRunning(false);
            setSyncMessage('');
            stopPolling();
            // Reload orders from local DB now that sync is done
            setPage(1);
            fetchOrders('', selectedStatuses, 1);
            return;
          }

          if (status === 'error' || status === 'unavailable') {
            setSyncRunning(false);
            setSyncMessage('');
            stopPolling();
            setError(data?.sync?.last_sync_message || 'Falha na sincronização. Verifique backend/worker.');
            return;
          }

          // Safety timeout: queue not consumed or worker down.
          if (pollAttemptsRef.current >= 40) {
            setSyncRunning(false);
            setSyncMessage('');
            stopPolling();
            setError('Sincronização não respondeu a tempo. Verifique se o Celery Worker e Beat estão rodando.');
          }
        })
        .catch(() => {
          pollAttemptsRef.current += 1;
          if (pollAttemptsRef.current >= 40) {
            setSyncRunning(false);
            setSyncMessage('');
            stopPolling();
            setError('Não foi possível obter status da sincronização. Verifique o backend.');
          }
        });
    }, 3000);
  }, [stopPolling, fetchOrders, selectedStatuses]);

  // Cleanup polling on unmount
  useEffect(() => () => stopPolling(), [stopPolling]);

  const triggerSync = useCallback(async (mode) => {
    try {
      setSyncRunning(true);
      setSyncMessage(`Sync ${mode} iniciado. Aguardando Celery processar…`);
      setError(null);
      const endpoint = mode === 'full' ? '/orders/sync/full' : '/orders/sync/incremental';
      const resp = await fetch(`${API_BASE}${endpoint}`, { method: 'POST' });
      const data = await resp.json().catch(() => ({}));
      if (!resp.ok) {
        setSyncRunning(false);
        setSyncMessage('');
        throw new Error(data.detail || `Falha no sync ${mode}`);
      }
      // Task was queued. Poll status until done.
      setSyncMessage(data.message || `Sync ${mode} em execução no Celery…`);
      startPolling();
    } catch (err) {
      setSyncRunning(false);
      setSyncMessage('');
      setError(err.message);
    }
  }, [startPolling]);

  // Fetch when page or statuses change
  useEffect(() => {
    fetchOrders(search, selectedStatuses, page);
  }, [page, selectedStatuses]); // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => {
    fetchSyncStatus();
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  // Debounced search
  const handleSearchChange = (e) => {
    const val = e.target.value;
    setSearch(val);
    if (debounceRef.current) clearTimeout(debounceRef.current);
    debounceRef.current = setTimeout(() => {
      setPage(1);
      fetchOrders(val, selectedStatuses, 1);
    }, 400);
  };

  const toggleStatus = (id) => {
    setSelectedStatuses((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
    setPage(1);
  };

  const toggleOrder = (orderId) => {
    setExpandedOrderId(expandedOrderId === orderId ? null : orderId);
  };

  const refresh = () => fetchOrders(search, selectedStatuses, page);

  const isEmptyDb = sourceMode === 'empty-db';
  const progress = syncStatus?.sync?.progress || { percent: 0, processed: 0, total: 0, upserted: 0, failed: 0 };
  const progressPercent = Number.isFinite(progress.percent) ? progress.percent : 0;

  return (
    <Layout>
      <div className="page-inner">
        <div className="page-header">
          <div>
            <h2>Pedidos</h2>
            <p className="page-subtitle">Pedidos de venda do Bling</p>
          </div>
          <button className="btn-refresh" onClick={refresh} disabled={loading}>
            {loading ? '⟳ Atualizando…' : '⟳ Atualizar'}
          </button>
        </div>

        {error && <div className="error">{error}</div>}

        <div className="card" style={{ marginBottom: 16 }}>
          <div className="card-header" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
            <h3>🔄 Status da Sincronização</h3>
            <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
              <button className="btn-secondary" onClick={() => triggerSync('incremental')} disabled={syncRunning}>
                {syncRunning ? 'Sincronizando...' : 'Sync Incremental'}
              </button>
              <button className="btn-secondary" onClick={() => triggerSync('full')} disabled={syncRunning}>
                {syncRunning ? 'Sincronizando...' : 'Sync Full'}
              </button>
              <button className="btn-secondary" onClick={fetchSyncStatus} disabled={syncLoading}>
                {syncLoading ? 'Atualizando...' : 'Atualizar Status'}
              </button>
            </div>
          </div>

          {syncRunning && syncMessage && (
            <div style={{ padding: '12px 20px', background: '#eff6ff', borderTop: '1px solid #bfdbfe', color: '#1d4ed8', fontSize: 13 }}>
              ⟳ {syncMessage}
            </div>
          )}

          {(syncRunning || progressPercent > 0) && (
            <div style={{ padding: '10px 20px 0' }}>
              <div style={{ height: 10, borderRadius: 999, background: '#e2e8f0', overflow: 'hidden' }}>
                <div
                  style={{
                    height: '100%',
                    width: `${progressPercent}%`,
                    background: progressPercent >= 100 ? '#16a34a' : '#2563eb',
                    transition: 'width 0.5s ease',
                  }}
                />
              </div>
              <div style={{ marginTop: 6, fontSize: 12, color: '#475569', display: 'flex', justifyContent: 'space-between' }}>
                <span>{progressPercent}%</span>
                <span>{progress.processed}/{progress.total} processados</span>
              </div>
            </div>
          )}

          <div style={{ padding: '16px 20px', display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))', gap: 10 }}>
            <div><strong>Pedidos locais:</strong> {syncStatus?.snapshot?.total_orders ?? 0}</div>
            <div><strong>Último sync status:</strong> {syncStatus?.sync?.last_sync_status || 'never'}</div>
            <div><strong>Último sync full:</strong> {formatDateTime(syncStatus?.sync?.last_full_sync_at)}</div>
            <div><strong>Último sync incremental:</strong> {formatDateTime(syncStatus?.sync?.last_incremental_sync_at)}</div>
            <div><strong>Último sync com sucesso:</strong> {formatDateTime(syncStatus?.sync?.last_successful_sync_at)}</div>
            <div><strong>Último pedido no snapshot:</strong> {formatDateTime(syncStatus?.snapshot?.latest_order_date)}</div>
            <div><strong>Fonte atual:</strong> {sourceMode || syncStatus?.source || '—'}</div>
            <div><strong>Upserts/erros:</strong> {progress.upserted ?? 0}/{progress.failed ?? 0}</div>
          </div>

          {(syncStatus?.sync?.last_sync_message || '').trim() && (
            <div style={{ padding: '0 20px 16px', color: '#64748b', fontSize: 13 }}>
              <strong>Mensagem:</strong> {syncStatus.sync.last_sync_message}
            </div>
          )}
        </div>

        {!hasBling && !loading && (
          <div className="info-box">
            <p>
              <strong>🔌 Bling não conectado.</strong> Autentique-se no Bling para sincronizar novos pedidos.
            </p>
          </div>
        )}

        {isEmptyDb && hasBling && !loading && (
          <div className="info-box" style={{ background: '#fef9c3', borderColor: '#fde047' }}>
            <p>
              <strong>📦 Banco local vazio.</strong> Clique em <strong>Sync Full</strong> para importar todos os pedidos do Bling. A importação roda em segundo plano via Celery — a página atualiza automaticamente quando concluir.
            </p>
          </div>
        )}

        {/* Filters */}
        <div className="card" style={{ marginBottom: 16 }}>
          <div style={{ padding: '16px 20px' }}>
            <div className="search-box" style={{ marginBottom: 12 }}>
              <input
                type="text"
                placeholder="Buscar por nº do pedido, nome do cliente ou nº Nuvemshop…"
                value={search}
                onChange={handleSearchChange}
              />
            </div>
            <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap', alignItems: 'center' }}>
              <span style={{ fontSize: 13, color: '#64748b', marginRight: 4 }}>Status:</span>
              {KNOWN_STATUSES.map((s) => (
                <button
                  key={s.id}
                  onClick={() => toggleStatus(s.id)}
                  style={{
                    cursor: 'pointer',
                    border: selectedStatuses.has(s.id) ? '2px solid #3b82f6' : '2px solid transparent',
                    padding: '5px 12px',
                    borderRadius: 16,
                    fontSize: 13,
                    fontWeight: selectedStatuses.has(s.id) ? 600 : 400,
                    background: selectedStatuses.has(s.id) ? '#dbeafe' : '#f1f5f9',
                    color: selectedStatuses.has(s.id) ? '#1d4ed8' : '#475569',
                    transition: 'all 0.15s ease',
                  }}
                >
                  {s.nome}
                </button>
              ))}
            </div>
          </div>
        </div>

        {/* Orders table */}
        <div className="card">
          <div className="card-header" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
            <h3>📋 Pedidos de Venda</h3>
            {!loading && <span style={{ fontSize: 13, color: '#94a3b8' }}>{total} pedido(s)</span>}
          </div>

          {loading && <p className="loading">Carregando pedidos…</p>}

          {!loading && orders.length === 0 && (
            <div className="empty-state">
              <span className="empty-state-icon">📭</span>
              <p>Nenhum pedido encontrado.</p>
            </div>
          )}

          {!loading && orders.length > 0 && (
            <>
              <table className="table">
                <thead>
                  <tr>
                    <th style={{ width: 40 }}></th>
                    <th>Nº Pedido</th>
                    <th>Nº Nuvemshop</th>
                    <th>Data</th>
                    <th>Cliente</th>
                    <th>Total</th>
                    <th>Situação</th>
                  </tr>
                </thead>
                <tbody>
                  {orders.map((order) => (
                    <React.Fragment key={order.id}>
                      <tr style={{ cursor: 'pointer', background: expandedOrderId === order.id ? '#f0f9ff' : undefined }} onClick={() => toggleOrder(order.id)}>
                        <td style={{ textAlign: 'center', color: '#64748b', paddingTop: 12, paddingBottom: 12 }}>
                          {order.itens && order.itens.length > 0 && (
                            <ChevronIcon isExpanded={expandedOrderId === order.id} />
                          )}
                        </td>
                        <td style={{ fontWeight: 600 }}>{order.numero ?? order.id}</td>
                        <td>{order.numeroLoja || '—'}</td>
                        <td>{order.data ? new Date(order.data).toLocaleDateString('pt-BR') : '—'}</td>
                        <td>{order.cliente}</td>
                        <td style={{ fontWeight: 600 }}>{formatBRL(order.total)}</td>
                        <td><StatusBadge text={order.situacao} /></td>
                      </tr>
                      {expandedOrderId === order.id && order.itens && order.itens.length > 0 && (
                        <tr style={{ background: '#f8fafc', borderTop: '2px solid #e2e8f0' }}>
                          <td colSpan="7" style={{ padding: '16px 20px' }}>
                            <div style={{ marginBottom: 12 }}>
                              <h4 style={{ margin: '0 0 12px 0', color: '#1e293b', fontSize: 14 }}>📦 Produtos</h4>
                              <table style={{ width: '100%', fontSize: 13, borderCollapse: 'collapse' }}>
                                <thead>
                                  <tr style={{ borderBottom: '1px solid #cbd5e1' }}>
                                    <th style={{ textAlign: 'left', padding: '8px', fontWeight: 600, color: '#475569' }}>SKU</th>
                                    <th style={{ textAlign: 'left', padding: '8px', fontWeight: 600, color: '#475569' }}>Produto</th>
                                    <th style={{ textAlign: 'right', padding: '8px', fontWeight: 600, color: '#475569', width: 80 }}>Qtd</th>
                                    <th style={{ textAlign: 'right', padding: '8px', fontWeight: 600, color: '#475569', width: 100 }}>Unit.</th>
                                    <th style={{ textAlign: 'right', padding: '8px', fontWeight: 600, color: '#475569', width: 100 }}>Total</th>
                                  </tr>
                                </thead>
                                <tbody>
                                  {order.itens.map((item, idx) => (
                                    <tr key={idx} style={{ borderBottom: '1px solid #f1f5f9' }}>
                                      <td style={{ padding: '8px', color: '#64748b', fontFamily: 'monospace' }}>{item.sku || '—'}</td>
                                      <td style={{ padding: '8px', color: '#334155' }}>{item.product_name}</td>
                                      <td style={{ textAlign: 'right', padding: '8px', color: '#64748b' }}>{item.quantity}</td>
                                      <td style={{ textAlign: 'right', padding: '8px', color: '#64748b' }}>{formatBRL(item.paid_unit_price ?? item.unit_price)}</td>
                                      <td style={{ textAlign: 'right', padding: '8px', fontWeight: 600, color: '#1e293b' }}>{formatBRL(item.paid_total ?? item.total)}</td>
                                    </tr>
                                  ))}
                                </tbody>
                              </table>
                            </div>
                          </td>
                        </tr>
                      )}
                    </React.Fragment>
                  ))}
                </tbody>
              </table>

              {totalPages > 1 && (
                <div style={{ display: 'flex', justifyContent: 'center', alignItems: 'center', gap: 12, padding: '16px 0' }}>
                  <button
                    className="btn-refresh"
                    onClick={() => setPage((p) => Math.max(1, p - 1))}
                    disabled={page <= 1}
                    style={{ minWidth: 'auto', padding: '6px 14px' }}
                  >
                    ← Anterior
                  </button>
                  <span style={{ fontSize: 13, color: '#64748b' }}>
                    Página {page} de {totalPages}
                  </span>
                  <button
                    className="btn-refresh"
                    onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
                    disabled={page >= totalPages}
                    style={{ minWidth: 'auto', padding: '6px 14px' }}
                  >
                    Próxima →
                  </button>
                </div>
              )}
            </>
          )}
        </div>
      </div>
    </Layout>
  );
}
