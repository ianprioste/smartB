import React, { useEffect, useState, useCallback, useRef, useMemo } from 'react';
import { Layout } from '../../components/Layout';
import { ProductionStatusBadge, ProductionNotesInput } from '../../components/ProductionControls';
import { ItemsFilterTab } from '../../components/ItemsFilterTab';
import useIsMobile from '../../hooks/useIsMobile';
import { useVersionPolling } from '../../hooks/useVersionPolling';

const API_BASE = '/api';

const KNOWN_STATUSES = [
  { id: 6, nome: 'Em aberto', color: '#eab308', bg: '#fefce8' },
  { id: 9, nome: 'Atendido', color: '#16a34a', bg: '#f0fdf4' },
  { id: 15, nome: 'Cancelado', color: '#dc2626', bg: '#fef2f2' },
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
  let bg = '#f1f5f9', color = '#64748b';
  if (lower.includes('atendido') || lower.includes('conclu') || lower.includes('entregue')) { bg = '#dcfce7'; color = '#15803d'; }
  else if (lower.includes('pendente') || lower.includes('aberto') || lower.includes('andamento')) { bg = '#fef9c3'; color = '#a16207'; }
  else if (lower.includes('cancel') || lower.includes('devolvido')) { bg = '#fee2e2'; color = '#b91c1c'; }
  return (
    <span style={{ display: 'inline-block', padding: '3px 10px', borderRadius: 12, fontSize: 12, fontWeight: 600, background: bg, color }}>{text || '—'}</span>
  );
}

function ChevronIcon({ isExpanded }) {
  return (
    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"
      style={{ transform: isExpanded ? 'rotate(90deg)' : 'rotate(0deg)', transition: 'transform 0.2s ease', display: 'block' }}>
      <polyline points="9 18 15 12 9 6" />
    </svg>
  );
}

/* ── Sync Modal ─────────────────────────────────────────────── */
function SyncModal({ open, onClose, syncStatus, syncRunning, syncMessage, onSync, onRefresh, syncLoading }) {
  if (!open) return null;
  const progress = syncStatus?.sync?.progress || {};
  const pct = Number.isFinite(progress.percent) ? progress.percent : 0;
  const snap = syncStatus?.snapshot || {};
  const sync = syncStatus?.sync || {};
  const isRunning = syncRunning || sync.last_sync_status === 'running';

  return (
    <>
      {/* Overlay */}
      <div onClick={onClose} style={{
        position: 'fixed', inset: 0, background: 'rgba(0,0,0,.35)', zIndex: 999,
        animation: 'fadeIn .15s ease',
      }} />
      {/* Panel */}
      <div style={{
        position: 'fixed', top: 0, right: 0, bottom: 0, width: '100%', maxWidth: 420,
        background: '#fff', zIndex: 1000, display: 'flex', flexDirection: 'column',
        boxShadow: '-4px 0 24px rgba(0,0,0,.12)', animation: 'slideIn .2s ease',
      }}>
        {/* Header */}
        <div style={{ padding: '20px 24px', borderBottom: '1px solid #e2e8f0', display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
          <h3 style={{ margin: 0, fontSize: 16, fontWeight: 700, color: '#0f172a' }}>Sincronização</h3>
          <button onClick={onClose} style={{ background: 'none', border: 'none', cursor: 'pointer', padding: 4, color: '#94a3b8', fontSize: 20, lineHeight: 1 }}>✕</button>
        </div>

        {/* Body */}
        <div style={{ flex: 1, overflowY: 'auto', padding: '20px 24px' }}>
          {/* Progress */}
          {isRunning && (
            <div style={{ marginBottom: 20 }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 6, fontSize: 13, color: '#475569' }}>
                <span style={{ fontWeight: 600 }}>Sincronizando…</span>
                <span>{pct}%</span>
              </div>
              <div style={{ height: 8, borderRadius: 99, background: '#e2e8f0', overflow: 'hidden' }}>
                <div style={{
                  height: '100%', width: `${pct}%`, borderRadius: 99,
                  background: pct >= 100 ? '#16a34a' : 'linear-gradient(90deg, #3b82f6, #6366f1)',
                  transition: 'width .5s ease',
                }} />
              </div>
              <div style={{ marginTop: 6, fontSize: 12, color: '#94a3b8' }}>
                {progress.processed ?? 0} / {progress.total ?? 0} pedidos • {progress.upserted ?? 0} atualizados • {progress.failed ?? 0} erros
              </div>
              {syncMessage && (
                <div style={{ marginTop: 8, padding: '8px 12px', background: '#eff6ff', borderRadius: 8, fontSize: 12, color: '#1d4ed8' }}>
                  {syncMessage}
                </div>
              )}
            </div>
          )}

          {/* Stats grid */}
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12, marginBottom: 20 }}>
            <StatCard label="Pedidos locais" value={snap.total_orders ?? 0} />
            <StatCard label="Status" value={sync.last_sync_status === 'ok' ? '✓ OK' : sync.last_sync_status === 'running' ? '⟳ Rodando' : sync.last_sync_status || 'Nunca'} color={sync.last_sync_status === 'ok' ? '#16a34a' : sync.last_sync_status === 'error' ? '#dc2626' : '#64748b'} />
          </div>

          {/* Timeline */}
          <div style={{ marginBottom: 20 }}>
            <h4 style={{ margin: '0 0 12px', fontSize: 13, fontWeight: 700, color: '#475569', textTransform: 'uppercase', letterSpacing: '.5px' }}>Histórico</h4>
            <TimelineItem label="Último sync full" value={formatDateTime(sync.last_full_sync_at)} />
            <TimelineItem label="Último sync incremental" value={formatDateTime(sync.last_incremental_sync_at)} />
            <TimelineItem label="Último sync com sucesso" value={formatDateTime(sync.last_successful_sync_at)} />
            <TimelineItem label="Pedido mais recente" value={formatDateTime(snap.latest_order_date)} />
          </div>

          {(sync.last_sync_message || '').trim() && (
            <div style={{ padding: '10px 14px', background: '#f8fafc', borderRadius: 8, fontSize: 12, color: '#64748b', wordBreak: 'break-all' }}>
              {sync.last_sync_message}
            </div>
          )}
        </div>

        {/* Footer actions */}
        <div style={{ padding: '16px 24px', borderTop: '1px solid #e2e8f0', display: 'flex', gap: 8 }}>
          <button onClick={() => onSync('incremental')} disabled={isRunning}
            style={{ flex: 1, padding: '10px 0', borderRadius: 8, border: '1px solid #e2e8f0', background: '#fff', color: '#334155', fontWeight: 600, fontSize: 13, cursor: isRunning ? 'not-allowed' : 'pointer', opacity: isRunning ? 0.5 : 1 }}>
            ⟳ Incremental
          </button>
          <button onClick={() => onSync('full')} disabled={isRunning}
            style={{ flex: 1, padding: '10px 0', borderRadius: 8, border: 'none', background: isRunning ? '#94a3b8' : '#2563eb', color: '#fff', fontWeight: 600, fontSize: 13, cursor: isRunning ? 'not-allowed' : 'pointer' }}>
            ↻ Sync Completo
          </button>
        </div>
      </div>

      <style>{`
        @keyframes fadeIn { from { opacity: 0 } to { opacity: 1 } }
        @keyframes slideIn { from { transform: translateX(100%) } to { transform: translateX(0) } }
      `}</style>
    </>
  );
}

function StatCard({ label, value, color }) {
  return (
    <div style={{ background: '#f8fafc', borderRadius: 10, padding: '14px 16px' }}>
      <div style={{ fontSize: 11, color: '#94a3b8', fontWeight: 600, textTransform: 'uppercase', letterSpacing: '.3px', marginBottom: 4 }}>{label}</div>
      <div style={{ fontSize: 18, fontWeight: 700, color: color || '#0f172a' }}>{value}</div>
    </div>
  );
}

function TimelineItem({ label, value }) {
  return (
    <div style={{ display: 'flex', justifyContent: 'space-between', padding: '8px 0', borderBottom: '1px solid #f1f5f9', fontSize: 13 }}>
      <span style={{ color: '#64748b' }}>{label}</span>
      <span style={{ color: '#334155', fontWeight: 500 }}>{value}</span>
    </div>
  );
}

/* ── Main Page ──────────────────────────────────────────────── */
export function OrdersPage() {
  const [orders, setOrders] = useState([]);
  const isMobile = useIsMobile(768);
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
  const [groupBy, setGroupBy] = useState('pedido');
  const [syncModalOpen, setSyncModalOpen] = useState(false);
  const debounceRef = useRef(null);
  const pollRef = useRef(null);
  const prevSyncStatusRef = useRef(null);
  const pollAttemptsRef = useRef(0);
  const deltaCursorRef = useRef(null);
  const suppressDeltaUntilRef = useRef(0);
  const isSyncRunningFlag = syncRunning || syncStatus?.sync?.last_sync_status === 'running';

  const markLocalMutation = useCallback(() => {
    suppressDeltaUntilRef.current = Date.now() + 4000;
  }, []);

  const handleProductionSaved = useCallback((sku, newStatus, newNotes, orderId) => {
    setOrders((prev) =>
      prev.map((order) => {
        if (orderId && Number(order.id) !== Number(orderId)) return order;
        const itens = (order.itens || []).map((item) => {
          if ((item.sku || '').toUpperCase() !== (sku || '').toUpperCase()) return item;
          return {
            ...item,
            ...(newStatus !== undefined ? { production_status: newStatus } : {}),
            ...(newNotes !== undefined ? { notes: newNotes } : {}),
          };
        });
        const embalado = itens.filter((i) => i.production_status === 'Embalado').length;
        return { ...order, itens, production_summary: `${embalado}/${itens.length} Embalado` };
      }),
    );
  }, []);

  const handleProductionStatusChange = useCallback(async (sku, currentStatus, nextStatus, orderId = null) => {
    if (nextStatus === currentStatus) return;
    try {
      await fetch(`${API_BASE}/orders/items/${encodeURIComponent(sku)}/production`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ production_status: nextStatus, bling_order_id: orderId }),
      });
      markLocalMutation();
      handleProductionSaved(sku, nextStatus, undefined, orderId);
    } catch (err) {
      console.error('Failed to save production status', err);
    }
  }, [handleProductionSaved, markLocalMutation]);

  const handleProductionNotesChange = useCallback((sku, productionStatus, notes, orderId = null) => {
    fetch(`${API_BASE}/orders/items/${encodeURIComponent(sku)}/production`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ production_status: productionStatus || 'Pendente', notes, bling_order_id: orderId }),
    }).catch(() => {});
    markLocalMutation();
    handleProductionSaved(sku, undefined, notes, orderId);
  }, [handleProductionSaved, markLocalMutation]);

  const handleOrderStatusChange = useCallback(async (orderId, newStatus) => {
    try {
      const resp = await fetch(`${API_BASE}/orders/orders/${orderId}/status`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ situacao: newStatus }),
      });
      if (!resp.ok) throw new Error('Falha ao atualizar status');
      markLocalMutation();
      setOrders((prev) =>
        prev.map((o) => o.id === orderId ? { ...o, situacao: newStatus } : o),
      );
    } catch (err) {
      alert(`Erro: ${err.message}`);
    }
  }, [markLocalMutation]);

  const fetchOrders = useCallback(async (searchTerm, statuses, pageNum) => {
    try {
      setLoading(true);
      setError(null);
      const statusStr = Array.from(statuses).join(',');
      const params = new URLSearchParams({ page: String(pageNum), limit: '50', statuses: statusStr });
      if (searchTerm) params.set('search', searchTerm);
      const resp = await fetch(`${API_BASE}/orders?${params}`);
      if (!resp.ok) throw new Error('Falha ao carregar pedidos');
      const data = await resp.json();
      setHasBling(data.has_bling_auth);
      setSourceMode(data.source || '');
      setOrders(data.data ?? []);
      setTotal(data.total ?? 0);
      setTotalPages(data.pages ?? 0);
      deltaCursorRef.current = new Date().toISOString();
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
    } catch { /* ignore */ } finally {
      setSyncLoading(false);
    }
  }, []);

  const fetchOrdersVersion = useCallback(async () => {
    const resp = await fetch(`${API_BASE}/orders/sync/version`);
    if (!resp.ok) return null;
    const data = await resp.json();
    if (data.last_updated_at) {
      deltaCursorRef.current = data.last_updated_at;
    }
    return data.current_version;
  }, []);

  const handleRemoteVersionChange = useCallback(async () => {
    if (Date.now() < suppressDeltaUntilRef.current) {
      return;
    }
    try {
      const params = new URLSearchParams();
      if (deltaCursorRef.current) {
        params.set('since', deltaCursorRef.current);
      }
      const resp = await fetch(`${API_BASE}/orders/sync/updates?${params.toString()}`);
      if (!resp.ok) {
        return;
      }
      const delta = await resp.json();
      if (delta.server_time) {
        deltaCursorRef.current = delta.server_time;
      }

      const statusMap = new Map((delta.order_status_updates || []).map((u) => [Number(u.order_id), u.situacao]));
      const notesUpdates = delta.production_updates || [];

      setOrders((prev) => prev.map((order) => {
        const orderId = Number(order.id);
        const nextStatus = statusMap.get(orderId);
        const itens = (order.itens || []).map((item) => {
          const sku = (item.sku || '').toUpperCase();
          const match = notesUpdates.find((u) => {
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
        const embalado = itens.filter((i) => i.production_status === 'Embalado').length;
        return {
          ...order,
          ...(nextStatus ? { situacao: nextStatus } : {}),
          itens,
          production_summary: `${embalado}/${itens.length} Embalado`,
        };
      }));
      fetchSyncStatus();
    } catch {
      // Keep current list stable; retry on next polling cycle.
    }
  }, [fetchSyncStatus]);

  const stopPolling = useCallback(() => {
    if (pollRef.current) { clearInterval(pollRef.current); pollRef.current = null; }
    pollAttemptsRef.current = 0;
  }, []);

  const startPolling = useCallback(() => {
    stopPolling();
    pollAttemptsRef.current = 0;
    pollRef.current = setInterval(() => {
      fetch(`${API_BASE}/orders/sync/status`).then(r => r.json()).then(data => {
        pollAttemptsRef.current += 1;
        const prevStatus = prevSyncStatusRef.current;
        const status = data?.sync?.last_sync_status;
        prevSyncStatusRef.current = status;
        setSyncStatus(data);
        if (status === 'ok' && prevStatus !== 'ok') {
          setSyncRunning(false); setSyncMessage(''); stopPolling();
          setPage(1); fetchOrders('', selectedStatuses, 1);
          return;
        }
        if (status === 'error' || status === 'unavailable') {
          setSyncRunning(false); setSyncMessage(''); stopPolling();
          setError(data?.sync?.last_sync_message || 'Falha na sincronização.');
          return;
        }
        if (pollAttemptsRef.current >= 120) {
          setSyncRunning(false); setSyncMessage(''); stopPolling();
          setError('Sincronização não respondeu a tempo.');
        }
      }).catch(() => {
        pollAttemptsRef.current += 1;
        if (pollAttemptsRef.current >= 120) { setSyncRunning(false); setSyncMessage(''); stopPolling(); }
      });
    }, 3000);
  }, [stopPolling, fetchOrders, selectedStatuses]);

  useEffect(() => () => stopPolling(), [stopPolling]);

  const triggerSync = useCallback(async (mode) => {
    try {
      setSyncRunning(true);
      setSyncMessage(mode === 'full' ? 'Importação completa iniciada…' : 'Atualização incremental iniciada…');
      setError(null);
      const endpoint = mode === 'full' ? '/orders/sync/full' : '/orders/sync/incremental';
      const resp = await fetch(`${API_BASE}${endpoint}`, { method: 'POST' });
      const data = await resp.json().catch(() => ({}));
      if (!resp.ok) { setSyncRunning(false); setSyncMessage(''); throw new Error(data.detail || `Falha no sync ${mode}`); }
      setSyncMessage(data.message || `Sync ${mode} em execução…`);
      startPolling();
    } catch (err) {
      setSyncRunning(false); setSyncMessage('');
      setError(err.message);
    }
  }, [startPolling]);

  useEffect(() => { fetchOrders(search, selectedStatuses, page); }, [page, selectedStatuses]); // eslint-disable-line
  useEffect(() => { fetchSyncStatus(); }, []); // eslint-disable-line

  useVersionPolling({
    enabled: hasBling && !isSyncRunningFlag,
    pollKey: 'orders_global',
    fetchVersion: fetchOrdersVersion,
    onVersionChange: handleRemoteVersionChange,
    intervalMsActive: 7000,
    intervalMsHidden: 15000,
  });

  const handleSearchChange = (e) => {
    const val = e.target.value;
    setSearch(val);
    if (debounceRef.current) clearTimeout(debounceRef.current);
    debounceRef.current = setTimeout(() => { setPage(1); fetchOrders(val, selectedStatuses, 1); }, 400);
  };

  const toggleStatus = (id) => {
    setSelectedStatuses(prev => { const next = new Set(prev); next.has(id) ? next.delete(id) : next.add(id); return next; });
    setPage(1);
  };

  const isEmptyDb = sourceMode === 'empty-db';
  const syncOk = syncStatus?.sync?.last_sync_status === 'ok';
  const localCount = syncStatus?.snapshot?.total_orders ?? 0;

  const groupedByItem = useMemo(() => {
    if (groupBy !== 'item') return [];
    const map = {};
    for (const order of orders) {
      for (const item of (order.itens || [])) {
        const key = (item.sku || item.product_name || '').toUpperCase();
        if (!key) continue;
        if (!map[key]) {
          map[key] = {
            sku: item.sku || '',
            product_name: item.product_name || '',
            total_qty: 0,
            total_paid: 0,
            orders: [],
          };
        }
        map[key].total_qty += Number(item.quantity || 0);
        map[key].total_paid += Number(item.paid_total ?? item.total ?? 0);
        map[key].orders.push({
          order_id: order.id,
          numero: order.numero,
          numero_loja: order.numeroLoja,
          data: order.data,
          cliente: order.cliente,
          situacao: order.situacao,
          quantity: item.quantity,
          paid_total: item.paid_total ?? item.total,
          production_status: item.production_status || 'Pendente',
          notes: item.notes || '',
        });
      }
    }
    return Object.values(map).sort((a, b) => (a.sku || '').localeCompare(b.sku || ''));
  }, [groupBy, orders]);

  return (
    <Layout>
      <div className="page-inner">
        {/* ── Header ── */}
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: 24, flexWrap: 'wrap', gap: 12 }}>
          <div>
            <h2 style={{ margin: 0, fontSize: 22, fontWeight: 800, color: '#0f172a' }}>Pedidos</h2>
            <p style={{ margin: '4px 0 0', fontSize: 13, color: '#94a3b8' }}>
              {total > 0 ? `${total} pedido(s) no banco local` : 'Pedidos de venda do Bling'}
            </p>
          </div>
          <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
            {/* Sync indicator pill */}
            <button onClick={() => setSyncModalOpen(true)} style={{
              display: 'flex', alignItems: 'center', gap: 6, padding: '7px 14px', borderRadius: 20,
              border: '1px solid #e2e8f0', background: '#fff', cursor: 'pointer', fontSize: 13, fontWeight: 500,
              color: isSyncRunningFlag ? '#2563eb' : syncOk ? '#16a34a' : '#64748b',
            }}>
              <span style={{
                width: 8, height: 8, borderRadius: '50%',
                background: isSyncRunningFlag ? '#3b82f6' : syncOk ? '#22c55e' : '#94a3b8',
                animation: isSyncRunningFlag ? 'pulse 1.5s infinite' : 'none',
              }} />
              {isSyncRunningFlag ? 'Sincronizando…' : `${localCount} sincronizados`}
            </button>
            <button onClick={() => fetchOrders(search, selectedStatuses, page)} disabled={loading}
              style={{ padding: '7px 14px', borderRadius: 8, border: '1px solid #e2e8f0', background: '#fff', cursor: 'pointer', fontSize: 13, color: '#475569', fontWeight: 500 }}>
              {loading ? '⟳' : '⟳ Atualizar'}
            </button>
          </div>
        </div>

        {error && <div style={{ padding: '12px 16px', background: '#fef2f2', border: '1px solid #fecaca', borderRadius: 10, color: '#b91c1c', fontSize: 13, marginBottom: 16 }}>{error}</div>}

        {!hasBling && !loading && (
          <div style={{ padding: '16px 20px', background: '#eff6ff', border: '1px solid #bfdbfe', borderRadius: 10, marginBottom: 16, fontSize: 13, color: '#1d4ed8' }}>
            🔌 <strong>Bling não conectado.</strong> Autentique-se no Bling para sincronizar pedidos.
          </div>
        )}

        {isEmptyDb && hasBling && !loading && (
          <div style={{ padding: '16px 20px', background: '#fefce8', border: '1px solid #fde047', borderRadius: 10, marginBottom: 16, display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 12, flexWrap: 'wrap' }}>
            <span style={{ fontSize: 13, color: '#854d0e' }}>📦 Banco local vazio. Importe os pedidos para começar.</span>
            <button onClick={() => { setSyncModalOpen(true); triggerSync('full'); }}
              style={{ padding: '8px 16px', borderRadius: 8, border: 'none', background: '#2563eb', color: '#fff', fontWeight: 600, fontSize: 13, cursor: 'pointer', whiteSpace: 'nowrap' }}>
              Importar pedidos
            </button>
          </div>
        )}

        {/* ── Filters ── */}
        <div style={{ display: 'flex', gap: 10, marginBottom: 16, flexWrap: 'wrap', alignItems: 'center' }}>
          <div style={{ flex: 1, minWidth: 220 }}>
            <input type="text" placeholder="Buscar por nº pedido, cliente ou Nuvemshop…" value={search} onChange={handleSearchChange}
              style={{ width: '100%', padding: '10px 14px', borderRadius: 10, border: '1px solid #e2e8f0', fontSize: 14, outline: 'none', background: '#fff', color: '#0f172a', boxSizing: 'border-box' }} />
          </div>
          <div style={{ display: 'flex', gap: 6 }}>
            {KNOWN_STATUSES.map(s => {
              const active = selectedStatuses.has(s.id);
              return (
                <button key={s.id} onClick={() => toggleStatus(s.id)}
                  style={{ padding: '8px 14px', borderRadius: 20, fontSize: 12, fontWeight: 600, cursor: 'pointer', transition: 'all .15s',
                    border: active ? `1.5px solid ${s.color}` : '1.5px solid transparent',
                    background: active ? s.bg : '#f1f5f9', color: active ? s.color : '#94a3b8' }}>
                  {s.nome}
                </button>
              );
            })}
          </div>
          <div style={{ display: 'flex', gap: 6 }}>
            {[{ key: 'pedido', label: 'Por Pedido' }, { key: 'item', label: 'Por Item' }].map((opt) => {
              const active = groupBy === opt.key;
              return (
                <button
                  key={opt.key}
                  onClick={() => { setGroupBy(opt.key); setExpandedOrderId(null); }}
                  style={{
                    padding: '8px 14px',
                    borderRadius: 20,
                    fontSize: 12,
                    fontWeight: 600,
                    cursor: 'pointer',
                    transition: 'all .15s',
                    border: active ? '1.5px solid #2563eb' : '1.5px solid transparent',
                    background: active ? '#dbeafe' : '#f1f5f9',
                    color: active ? '#1d4ed8' : '#64748b',
                  }}
                >
                  {opt.label}
                </button>
              );
            })}
          </div>
        </div>

        {/* ── Table ── */}
        <div style={{ background: '#fff', borderRadius: 12, border: '1px solid #e2e8f0', overflow: 'hidden' }}>
          {loading && <div style={{ padding: 48, textAlign: 'center', color: '#94a3b8' }}>Carregando pedidos…</div>}

          {!loading && orders.length === 0 && (
            <div style={{ padding: 48, textAlign: 'center' }}>
              <div style={{ fontSize: 36, marginBottom: 8 }}>📭</div>
              <p style={{ color: '#94a3b8', fontSize: 14, margin: 0 }}>Nenhum pedido encontrado.</p>
            </div>
          )}

          {!loading && orders.length > 0 && (
            <>
              {groupBy === 'item' ? (
                <ItemsFilterTab
                  groups={groupedByItem}
                  isMobile={isMobile}
                  expandedKey={expandedOrderId}
                  onToggle={(key) => setExpandedOrderId(expandedOrderId === key ? null : key)}
                  formatCurrency={formatBRL}
                  renderStatus={(situacao) => <StatusBadge text={situacao} />}
                  onChangeStatus={(sku, order, nextStatus) => handleProductionStatusChange(sku, order.production_status, nextStatus, order.order_id)}
                  onChangeNotes={(sku, order, notes) => handleProductionNotesChange(sku, order.production_status, notes, order.order_id)}
                />
              ) : isMobile ? (
                <div style={{ padding: 12, display: 'grid', gap: 12 }}>
                  {orders.map((order) => {
                    const itens = order.itens || [];
                    const expanded = expandedOrderId === order.id;
                    const allEmbalado = itens.length > 0 && itens.every((i) => i.production_status === 'Embalado');

                    return (
                      <div key={order.id} style={{ border: '1px solid #e2e8f0', borderRadius: 10, overflow: 'hidden', background: '#fff' }}>
                        <button
                          onClick={() => setExpandedOrderId(expanded ? null : order.id)}
                          style={{ width: '100%', textAlign: 'left', border: 'none', background: expanded ? '#f8fafc' : '#fff', padding: 14, cursor: 'pointer' }}
                        >
                          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: 8, marginBottom: 8 }}>
                            <div style={{ fontWeight: 700, color: '#0f172a' }}>Pedido {order.numero ?? order.id} • {order.cliente || '—'}</div>
                            <div style={{ fontWeight: 700, color: '#0f172a' }}>{formatBRL(order.total)}</div>
                          </div>

                          <div style={{ display: 'grid', gap: 6 }}>
                            <div style={{ fontSize: 12, color: '#64748b' }}><strong>Data:</strong> {order.data ? new Date(order.data).toLocaleDateString('pt-BR') : '—'}</div>
                            <div style={{ fontSize: 12, color: '#475569' }}><strong>Código:</strong> {order.numeroLoja || '—'}</div>
                            <div style={{ display: 'flex', alignItems: 'center', gap: 8, flexWrap: 'wrap' }}>
                              <StatusBadge text={order.situacao} />
                              <span style={{ fontSize: 12, color: '#64748b' }}>{order.production_summary || '—'}</span>
                              <span title={order.has_frete ? 'Envio' : 'Retirada'}>{order.has_frete ? '🚚' : '🏪'}</span>
                              {itens.length > 0 && <ChevronIcon isExpanded={expanded} />}
                            </div>
                          </div>
                        </button>

                        {expanded && itens.length > 0 && (
                          <div style={{ padding: 12, borderTop: '1px solid #e2e8f0', background: '#f8fafc' }}>
                            {allEmbalado && order.situacao !== 'Atendido' && (
                              <div style={{ marginBottom: 12 }}>
                                <button
                                  onClick={(e) => { e.stopPropagation(); handleOrderStatusChange(order.id, 'Atendido'); }}
                                  style={{ fontSize: 12, padding: '6px 12px', borderRadius: 8, border: '1px solid #16a34a', background: '#f0fdf4', color: '#15803d', fontWeight: 600, cursor: 'pointer' }}
                                >
                                  ✅ Marcar como Atendido
                                </button>
                              </div>
                            )}

                            <div style={{ display: 'grid', gap: 10 }}>
                              {itens.map((item, idx) => (
                                <div key={idx} style={{ border: '1px solid #e2e8f0', borderRadius: 8, background: '#fff', padding: 10 }}>
                                  <div style={{ fontSize: 12, color: '#64748b', fontFamily: 'monospace', marginBottom: 4 }}>{item.sku || '—'}</div>
                                  <div style={{ fontSize: 13, fontWeight: 600, color: '#334155', marginBottom: 8 }}>{item.product_name}</div>
                                  <div style={{ display: 'flex', justifyContent: 'space-between', gap: 8, fontSize: 12, color: '#64748b', marginBottom: 8 }}>
                                    <span><strong>Qtd:</strong> {item.quantity}</span>
                                    <span><strong>Total:</strong> {formatBRL(item.paid_total ?? item.total)}</span>
                                  </div>
                                  <div style={{ marginBottom: 8 }}>
                                    <ProductionStatusBadge
                                      status={item.production_status}
                                      onChangeStatus={(nextStatus) => handleProductionStatusChange(item.sku, item.production_status, nextStatus, order.id)}
                                    />
                                  </div>
                                  <ProductionNotesInput
                                    initialValue={item.notes}
                                    onChangeNotes={(notes) => handleProductionNotesChange(item.sku, item.production_status, notes, order.id)}
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
                <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 14 }}>
                  <thead>
                    <tr style={{ borderBottom: '2px solid #f1f5f9' }}>
                      <th style={{ width: 36, padding: '12px 8px' }}></th>
                      <th style={{ textAlign: 'left', padding: '12px 12px', fontWeight: 700, color: '#64748b', fontSize: 12, textTransform: 'uppercase', letterSpacing: '.3px' }}>Nº Pedido</th>
                      <th style={{ textAlign: 'left', padding: '12px 12px', fontWeight: 700, color: '#64748b', fontSize: 12, textTransform: 'uppercase', letterSpacing: '.3px' }}>Nuvemshop</th>
                      <th style={{ textAlign: 'left', padding: '12px 12px', fontWeight: 700, color: '#64748b', fontSize: 12, textTransform: 'uppercase', letterSpacing: '.3px' }}>Data</th>
                      <th style={{ textAlign: 'left', padding: '12px 12px', fontWeight: 700, color: '#64748b', fontSize: 12, textTransform: 'uppercase', letterSpacing: '.3px' }}>Cliente</th>
                      <th style={{ textAlign: 'center', padding: '12px 12px', fontWeight: 700, color: '#64748b', fontSize: 12, textTransform: 'uppercase', letterSpacing: '.3px' }}>Status</th>
                      <th style={{ textAlign: 'center', padding: '12px 12px', fontWeight: 700, color: '#64748b', fontSize: 12, textTransform: 'uppercase', letterSpacing: '.3px' }}>Produção</th>
                      <th style={{ width: 36, padding: '12px 4px' }}></th>
                      <th style={{ textAlign: 'right', padding: '12px 12px', fontWeight: 700, color: '#64748b', fontSize: 12, textTransform: 'uppercase', letterSpacing: '.3px' }}>Total</th>
                    </tr>
                  </thead>
                  <tbody>
                    {orders.map(order => {
                      const itens = order.itens || [];
                      const allEmbalado = itens.length > 0 && itens.every((i) => i.production_status === 'Embalado');
                      return (
                      <React.Fragment key={order.id}>
                        <tr onClick={() => setExpandedOrderId(expandedOrderId === order.id ? null : order.id)}
                          style={{ cursor: 'pointer', borderBottom: '1px solid #f1f5f9', transition: 'background .1s',
                            background: expandedOrderId === order.id ? '#f8fafc' : '#fff' }}
                          onMouseEnter={e => { if (expandedOrderId !== order.id) e.currentTarget.style.background = '#fafafa'; }}
                          onMouseLeave={e => { if (expandedOrderId !== order.id) e.currentTarget.style.background = '#fff'; }}>
                          <td style={{ textAlign: 'center', padding: '10px 8px', color: '#cbd5e1' }}>
                            {itens.length > 0 && <ChevronIcon isExpanded={expandedOrderId === order.id} />}
                          </td>
                          <td style={{ padding: '10px 12px', fontWeight: 700, color: '#0f172a' }}>{order.numero ?? order.id}</td>
                          <td style={{ padding: '10px 12px', color: '#64748b' }}>{order.numeroLoja || '—'}</td>
                          <td style={{ padding: '10px 12px', color: '#475569' }}>{order.data ? new Date(order.data).toLocaleDateString('pt-BR') : '—'}</td>
                          <td style={{ padding: '10px 12px', color: '#334155', maxWidth: 200, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{order.cliente}</td>
                          <td style={{ padding: '10px 12px', textAlign: 'center' }}><StatusBadge text={order.situacao} /></td>
                          <td style={{ padding: '10px 12px', textAlign: 'center', fontSize: 12, color: '#64748b' }}>{order.production_summary || '—'}</td>
                          <td style={{ padding: '10px 4px', fontSize: 14, textAlign: 'center' }} title={order.has_frete ? 'Envio' : 'Retirada'}>{order.has_frete ? '🚚' : '🏪'}</td>
                          <td style={{ padding: '10px 12px', textAlign: 'right', fontWeight: 700, color: '#0f172a' }}>{formatBRL(order.total)}</td>
                        </tr>
                        {expandedOrderId === order.id && itens.length > 0 && (
                          <tr>
                            <td colSpan="9" style={{ padding: 0 }}>
                              <div style={{ margin: '0 16px 12px', padding: 16, background: '#f8fafc', borderRadius: 8, border: '1px solid #e2e8f0' }}>
                                {allEmbalado && order.situacao !== 'Atendido' && (
                                  <div style={{ marginBottom: 12, display: 'flex', gap: 8 }}>
                                    <button
                                      onClick={(e) => { e.stopPropagation(); handleOrderStatusChange(order.id, 'Atendido'); }}
                                      style={{ fontSize: 12, padding: '4px 12px', borderRadius: 8, border: '1px solid #16a34a', background: '#f0fdf4', color: '#15803d', fontWeight: 600, cursor: 'pointer' }}>
                                      ✅ Marcar como Atendido
                                    </button>
                                  </div>
                                )}
                                <div style={{ fontSize: 12, fontWeight: 700, color: '#475569', marginBottom: 10, textTransform: 'uppercase', letterSpacing: '.3px' }}>Itens do pedido</div>
                                <table style={{ width: '100%', fontSize: 13, borderCollapse: 'collapse' }}>
                                  <thead>
                                    <tr style={{ borderBottom: '1px solid #e2e8f0' }}>
                                      <th style={{ textAlign: 'left', padding: '6px 8px', fontWeight: 600, color: '#94a3b8', fontSize: 11, textTransform: 'uppercase' }}>SKU</th>
                                      <th style={{ textAlign: 'left', padding: '6px 8px', fontWeight: 600, color: '#94a3b8', fontSize: 11, textTransform: 'uppercase' }}>Produto</th>
                                      <th style={{ textAlign: 'left', padding: '6px 8px', fontWeight: 600, color: '#94a3b8', fontSize: 11, textTransform: 'uppercase' }}>Produção</th>
                                      <th style={{ textAlign: 'right', padding: '6px 8px', fontWeight: 600, color: '#94a3b8', fontSize: 11, textTransform: 'uppercase', width: 60 }}>Qtd</th>
                                      <th style={{ textAlign: 'right', padding: '6px 8px', fontWeight: 600, color: '#94a3b8', fontSize: 11, textTransform: 'uppercase', width: 90 }}>Total</th>
                                      <th style={{ textAlign: 'left', padding: '6px 8px', fontWeight: 600, color: '#94a3b8', fontSize: 11, textTransform: 'uppercase' }}>Notas</th>
                                    </tr>
                                  </thead>
                                  <tbody>
                                    {itens.map((item, idx) => (
                                      <tr key={idx} style={{ borderBottom: '1px solid #f1f5f9' }}>
                                        <td style={{ padding: '7px 8px', color: '#64748b', fontFamily: 'monospace', fontSize: 12 }}>{item.sku || '—'}</td>
                                        <td style={{ padding: '7px 8px', color: '#334155' }}>{item.product_name}</td>
                                        <td style={{ padding: '7px 8px' }}>
                                          <ProductionStatusBadge
                                            status={item.production_status}
                                            onChangeStatus={(nextStatus) => handleProductionStatusChange(item.sku, item.production_status, nextStatus, order.id)}
                                          />
                                        </td>
                                        <td style={{ textAlign: 'right', padding: '7px 8px', color: '#64748b' }}>{item.quantity}</td>
                                        <td style={{ textAlign: 'right', padding: '7px 8px', fontWeight: 600, color: '#0f172a' }}>{formatBRL(item.paid_total ?? item.total)}</td>
                                        <td style={{ padding: '7px 8px', minWidth: 150 }}>
                                          <ProductionNotesInput
                                            initialValue={item.notes}
                                            onChangeNotes={(notes) => handleProductionNotesChange(item.sku, item.production_status, notes, order.id)}
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
              )}

              {totalPages > 1 && (
                <div style={{ display: 'flex', justifyContent: 'center', alignItems: 'center', gap: 12, padding: '14px 0', borderTop: '1px solid #f1f5f9' }}>
                  <button onClick={() => setPage(p => Math.max(1, p - 1))} disabled={page <= 1}
                    style={{ padding: '6px 14px', borderRadius: 8, border: '1px solid #e2e8f0', background: '#fff', cursor: page <= 1 ? 'not-allowed' : 'pointer', fontSize: 13, color: '#475569', opacity: page <= 1 ? .4 : 1 }}>
                    ← Anterior
                  </button>
                  <span style={{ fontSize: 13, color: '#94a3b8' }}>Página {page} de {totalPages}</span>
                  <button onClick={() => setPage(p => Math.min(totalPages, p + 1))} disabled={page >= totalPages}
                    style={{ padding: '6px 14px', borderRadius: 8, border: '1px solid #e2e8f0', background: '#fff', cursor: page >= totalPages ? 'not-allowed' : 'pointer', fontSize: 13, color: '#475569', opacity: page >= totalPages ? .4 : 1 }}>
                    Próxima →
                  </button>
                </div>
              )}
            </>
          )}
        </div>
      </div>

      {/* Sync side-panel */}
      <SyncModal
        open={syncModalOpen}
        onClose={() => setSyncModalOpen(false)}
        syncStatus={syncStatus}
        syncRunning={syncRunning}
        syncMessage={syncMessage}
        onSync={triggerSync}
        onRefresh={fetchSyncStatus}
        syncLoading={syncLoading}
      />

      <style>{`@keyframes pulse { 0%,100% { opacity:1 } 50% { opacity:.4 } }`}</style>
    </Layout>
  );
}
