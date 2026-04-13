import React, { useEffect, useState, useCallback, useRef } from 'react';
import { Layout } from '../../components/Layout';
import { ProductionStatusBadge, ProductionNotesInput } from '../../components/ProductionControls';
import useIsMobile from '../../hooks/useIsMobile';
import { useVersionPolling } from '../../hooks/useVersionPolling';

const API_BASE = '/api';
const ORDERS_UI_STATE_KEY = 'smartbling:orders:ui-state:v1';

const KNOWN_STATUSES = [
  { id: 6, nome: 'Em aberto', color: '#eab308', bg: '#fefce8' },
  { id: 9, nome: 'Atendido', color: '#16a34a', bg: '#f0fdf4' },
  { id: 15, nome: 'Cancelado', color: '#dc2626', bg: '#fef2f2' },
];

const DEFAULT_STATUS_IDS = [6, 9, 15];
const KNOWN_STATUS_IDS = new Set(KNOWN_STATUSES.map((status) => status.id));

function normalizeExpandedKey(value) {
  if (value == null || value === '') return null;
  return String(value);
}

function isExpandedMatch(current, next) {
  if (current == null || next == null) return false;
  return String(current) === String(next);
}

function getScrollContainer() {
  if (typeof document === 'undefined') return null;
  return document.querySelector('.page-content');
}

function getCurrentScrollY() {
  if (typeof window === 'undefined') return 0;
  const container = getScrollContainer();
  if (container) return container.scrollTop;
  return window.scrollY;
}

function restoreScrollY(value) {
  if (typeof window === 'undefined') return;
  const targetY = Number.isFinite(Number(value)) ? Math.max(0, Number(value)) : 0;
  const container = getScrollContainer();
  if (container) {
    container.scrollTop = targetY;
    return;
  }
  window.scrollTo(0, targetY);
}

function readSavedOrdersUiState() {
  if (typeof window === 'undefined') return null;
  try {
    const raw = window.localStorage.getItem(ORDERS_UI_STATE_KEY);
    if (!raw) return null;
    const parsed = JSON.parse(raw);
    const restoredStatuses = Array.isArray(parsed?.selectedStatuses)
      ? parsed.selectedStatuses
        .map((value) => Number(value))
        .filter((id) => KNOWN_STATUS_IDS.has(id))
      : DEFAULT_STATUS_IDS;
    return {
      search: typeof parsed?.search === 'string' ? parsed.search : '',
      selectedStatuses: new Set(restoredStatuses),
      page: Number.isFinite(Number(parsed?.page)) && Number(parsed.page) > 0 ? Number(parsed.page) : 1,
      expandedOrderId: normalizeExpandedKey(parsed?.expandedOrderId),
      scrollY: Number.isFinite(Number(parsed?.scrollY)) ? Math.max(0, Number(parsed.scrollY)) : 0,
    };
  } catch {
    return null;
  }
}

function persistOrdersUiState(state) {
  if (typeof window === 'undefined') return;
  try {
    window.localStorage.setItem(ORDERS_UI_STATE_KEY, JSON.stringify({
      search: state.search || '',
      selectedStatuses: Array.from(state.selectedStatuses || []),
      page: Number(state.page) > 0 ? Number(state.page) : 1,
      expandedOrderId: state.expandedOrderId ?? null,
      scrollY: Number.isFinite(Number(state.scrollY)) ? Math.max(0, Number(state.scrollY)) : 0,
    }));
  } catch {
    // Ignore persistence failures (private mode/quota).
  }
}

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

function OrderTagEditor({
  orderId,
  currentTags,
  availableTags,
  draftTagsByOrder,
  setDraftTagsByOrder,
  onAdd,
  onRemove,
  saving,
  error,
}) {
  const key = String(orderId || '');
  const datalistId = `global-order-tags-${key || 'unknown'}`;
  const value = key ? (draftTagsByOrder[key] ?? '') : '';
  const tags = Array.isArray(currentTags) ? currentTags.filter(Boolean) : [];

  return (
    <div onClick={(e) => e.stopPropagation()} style={{ display: 'grid', gap: 4 }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 6, flexWrap: 'wrap' }}>
        <input
          list={datalistId}
          value={value}
          onChange={(e) => {
            const next = e.target.value;
            setDraftTagsByOrder((prev) => ({ ...prev, [key]: next }));
          }}
          onKeyDown={(e) => {
            if (e.key === 'Enter') {
              e.preventDefault();
              if ((value || '').trim()) onAdd(orderId, value);
            }
          }}
          placeholder="Digite a tag"
          disabled={!key || saving}
          style={{ padding: '5px 8px', borderRadius: 8, border: '1px solid #cbd5e1', fontSize: 12, background: '#fff', color: '#334155', minWidth: 130 }}
        />
        <datalist id={datalistId}>
          {availableTags.map((tag) => (
            <option key={tag} value={tag} />
          ))}
        </datalist>
        {saving && <span style={{ fontSize: 11, color: '#64748b' }}>Salvando...</span>}
      </div>
      {tags.length > 0 && (
        <div style={{ display: 'flex', alignItems: 'center', gap: 6, flexWrap: 'wrap' }}>
          {tags.map((tag) => (
            <span key={tag} style={{ display: 'inline-flex', alignItems: 'center', gap: 6, padding: '2px 8px', borderRadius: 999, background: '#eff6ff', color: '#1d4ed8', fontSize: 11, fontWeight: 600 }}>
              {tag}
              <button
                type="button"
                onClick={() => onRemove(orderId, tag)}
                disabled={!key || saving}
                aria-label={`Remover tag ${tag}`}
                style={{ border: 'none', background: 'transparent', color: '#1d4ed8', fontSize: 12, fontWeight: 700, cursor: !key || saving ? 'not-allowed' : 'pointer', padding: 0, lineHeight: 1 }}
              >
                x
              </button>
            </span>
          ))}
        </div>
      )}
      {!!error && <span style={{ fontSize: 11, color: '#b91c1c' }}>{error}</span>}
    </div>
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
  const savedUiState = readSavedOrdersUiState();
  const [orders, setOrders] = useState([]);
  const isMobile = useIsMobile(1024);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [hasBling, setHasBling] = useState(false);
  const [syncStatus, setSyncStatus] = useState(null);
  const [syncLoading, setSyncLoading] = useState(false);
  const [syncRunning, setSyncRunning] = useState(false);
  const [sourceMode, setSourceMode] = useState('');
  const [search, setSearch] = useState(savedUiState?.search || '');
  const [selectedStatuses, setSelectedStatuses] = useState(() => savedUiState?.selectedStatuses || new Set(DEFAULT_STATUS_IDS));
  const [page, setPage] = useState(savedUiState?.page || 1);
  const [totalPages, setTotalPages] = useState(0);
  const [total, setTotal] = useState(0);
  const [syncMessage, setSyncMessage] = useState('');
  const [expandedOrderId, setExpandedOrderId] = useState(savedUiState?.expandedOrderId ?? null);
  const [syncModalOpen, setSyncModalOpen] = useState(false);
  const [availableTags, setAvailableTags] = useState([]);
  const [selectedTagFilter, setSelectedTagFilter] = useState('');
  const [draftTagsByOrder, setDraftTagsByOrder] = useState({});
  const [tagSavingByOrder, setTagSavingByOrder] = useState({});
  const [tagErrorByOrder, setTagErrorByOrder] = useState({});
  const initialScrollYRef = useRef(savedUiState?.scrollY || 0);
  const hasRestoredScrollRef = useRef(false);
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

  const handleProductionSaved = useCallback((sku, newStatus, newNotes) => {
    setOrders((prev) =>
      prev.map((order) => {
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

  const handleProductionStatusChange = useCallback(async (sku, currentStatus, nextStatus) => {
    if (nextStatus === currentStatus) return;
    try {
      await fetch(`${API_BASE}/orders/items/${encodeURIComponent(sku)}/production`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ production_status: nextStatus }),
      });
      markLocalMutation();
      handleProductionSaved(sku, nextStatus, undefined);
    } catch (err) {
      console.error('Failed to save production status', err);
    }
  }, [handleProductionSaved, markLocalMutation]);

  const handleProductionNotesChange = useCallback((sku, productionStatus, notes) => {
    fetch(`${API_BASE}/orders/items/${encodeURIComponent(sku)}/production`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ production_status: productionStatus || 'Pendente', notes }),
    }).catch(() => {});
    markLocalMutation();
    handleProductionSaved(sku, undefined, notes);
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

  const fetchGlobalTags = useCallback(async () => {
    try {
      const resp = await fetch(`${API_BASE}/orders/tags`);
      if (!resp.ok) return;
      const data = await resp.json();
      setAvailableTags((data.tags || []).map((t) => t.name).filter(Boolean));
    } catch {
      // Keep page functional even if tags endpoint fails.
    }
  }, []);

  const handleOrderTagAdd = useCallback(async (orderId, rawTag) => {
    const key = String(orderId || '');
    if (!key) {
      setTagErrorByOrder((prev) => ({ ...prev, [key]: 'Pedido sem ID válido para salvar tag' }));
      return;
    }

    const chosenTag = (rawTag || '').trim();
    setTagSavingByOrder((prev) => ({ ...prev, [key]: true }));
    setTagErrorByOrder((prev) => ({ ...prev, [key]: '' }));
    try {
      if (!chosenTag) return;

      const resp = await fetch(`${API_BASE}/orders/${orderId}/tag`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ tag_name: chosenTag }),
      });
      if (!resp.ok) {
        const data = await resp.json().catch(() => ({}));
        throw new Error(data.detail || 'Falha ao salvar tag');
      }
      const data = await resp.json();
      const resolvedTags = Array.isArray(data.tags) ? data.tags : ((data.tag || '').trim() ? [String(data.tag).trim()] : [chosenTag]);
      setOrders((prev) => prev.map((o) => (o.id === orderId ? { ...o, tags: resolvedTags, tag: resolvedTags[0] || null } : o)));
      setAvailableTags((prev) => Array.from(new Set([...prev, ...resolvedTags])).sort((a, b) => a.localeCompare(b, 'pt-BR')));
      setDraftTagsByOrder((prev) => ({ ...prev, [key]: '' }));
      markLocalMutation();
    } catch (err) {
      setTagErrorByOrder((prev) => ({ ...prev, [key]: err.message || 'Erro ao salvar tag' }));
    } finally {
      setTagSavingByOrder((prev) => ({ ...prev, [key]: false }));
    }
  }, [markLocalMutation]);

  const handleOrderTagRemove = useCallback(async (orderId, tagName) => {
    const key = String(orderId || '');
    if (!key || !(tagName || '').trim()) return;

    setTagSavingByOrder((prev) => ({ ...prev, [key]: true }));
    setTagErrorByOrder((prev) => ({ ...prev, [key]: '' }));
    try {
      const params = new URLSearchParams({ tag_name: tagName });
      const resp = await fetch(`${API_BASE}/orders/${orderId}/tag?${params.toString()}`, { method: 'DELETE' });
      if (!resp.ok) {
        const data = await resp.json().catch(() => ({}));
        throw new Error(data.detail || 'Falha ao remover tag');
      }
      const data = await resp.json();
      const resolvedTags = Array.isArray(data.tags) ? data.tags : [];
      setOrders((prev) => prev.map((o) => (o.id === orderId ? { ...o, tags: resolvedTags, tag: resolvedTags[0] || null } : o)));
      await fetchGlobalTags();
      markLocalMutation();
    } catch (err) {
      setTagErrorByOrder((prev) => ({ ...prev, [key]: err.message || 'Erro ao remover tag' }));
    } finally {
      setTagSavingByOrder((prev) => ({ ...prev, [key]: false }));
    }
  }, [fetchGlobalTags, markLocalMutation]);

  const fetchOrders = useCallback(async (searchTerm, statuses, pageNum, selectedTag = '') => {
    try {
      setLoading(true);
      setError(null);
      const statusStr = Array.from(statuses).join(',');
      const params = new URLSearchParams({ page: String(pageNum), limit: '50', statuses: statusStr });
      if (searchTerm) params.set('search', searchTerm);
      if (selectedTag) params.set('tag', selectedTag);
      const resp = await fetch(`${API_BASE}/orders?${params}`);
      if (!resp.ok) throw new Error('Falha ao carregar pedidos');
      const data = await resp.json();
      setHasBling(data.has_bling_auth);
      setSourceMode(data.source || '');
      setOrders((data.data ?? []).map((order) => ({
        ...order,
        tags: Array.isArray(order.tags) ? order.tags : ((order.tag || '').trim() ? [order.tag] : []),
      })));
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
          setPage(1); fetchOrders('', selectedStatuses, 1, selectedTagFilter);
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
  }, [stopPolling, fetchOrders, selectedStatuses, selectedTagFilter]);

  useEffect(() => () => stopPolling(), [stopPolling]);

  useEffect(() => {
    persistOrdersUiState({
      search,
      selectedStatuses,
      page,
      expandedOrderId,
      scrollY: getCurrentScrollY(),
    });
  }, [search, selectedStatuses, page, expandedOrderId]);

  useEffect(() => {
    if (typeof window === 'undefined') return undefined;
    const persistOnUnload = () => {
      persistOrdersUiState({
        search,
        selectedStatuses,
        page,
        expandedOrderId,
        scrollY: getCurrentScrollY(),
      });
    };
    window.addEventListener('beforeunload', persistOnUnload);
    return () => window.removeEventListener('beforeunload', persistOnUnload);
  }, [search, selectedStatuses, page, expandedOrderId]);

  useEffect(() => {
    if (loading || hasRestoredScrollRef.current || typeof window === 'undefined') return;
    hasRestoredScrollRef.current = true;
    if (initialScrollYRef.current > 0) {
      window.requestAnimationFrame(() => {
        restoreScrollY(initialScrollYRef.current);
      });
    }
  }, [loading]);

  useEffect(() => {
    if (totalPages > 0 && page > totalPages) {
      setPage(1);
    }
  }, [page, totalPages]);

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

  useEffect(() => { fetchOrders(search, selectedStatuses, page, selectedTagFilter); }, [page, selectedStatuses, selectedTagFilter]); // eslint-disable-line
  useEffect(() => { fetchSyncStatus(); }, []); // eslint-disable-line
  useEffect(() => { fetchGlobalTags(); }, [fetchGlobalTags]);

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
    debounceRef.current = setTimeout(() => { setPage(1); fetchOrders(val, selectedStatuses, 1, selectedTagFilter); }, 400);
  };

  const toggleStatus = (id) => {
    setSelectedStatuses(prev => { const next = new Set(prev); next.has(id) ? next.delete(id) : next.add(id); return next; });
    setPage(1);
  };

  const isEmptyDb = sourceMode === 'empty-db';
  const syncOk = syncStatus?.sync?.last_sync_status === 'ok';
  const localCount = syncStatus?.snapshot?.total_orders ?? 0;

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
            <button onClick={() => fetchOrders(search, selectedStatuses, page, selectedTagFilter)} disabled={loading}
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
          <div>
            <select
              value={selectedTagFilter}
              onChange={(e) => { setSelectedTagFilter(e.target.value); setPage(1); }}
              style={{ padding: '9px 10px', borderRadius: 10, border: '1px solid #e2e8f0', fontSize: 13, color: '#334155', background: '#fff' }}
            >
              <option value="">Todas as tags</option>
              {availableTags.map((tag) => (
                <option key={tag} value={tag}>{tag}</option>
              ))}
            </select>
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
              {isMobile ? (
                <div style={{ padding: 12, display: 'grid', gap: 12 }}>
                  {orders.map((order) => {
                    const itens = order.itens || [];
                    const expanded = isExpandedMatch(expandedOrderId, order.id);
                    const allEmbalado = itens.length > 0 && itens.every((i) => i.production_status === 'Embalado');

                    return (
                      <div key={order.id} style={{ border: '1px solid #e2e8f0', borderRadius: 10, overflow: 'hidden', background: '#fff' }}>
                        <button
                          onClick={() => setExpandedOrderId(expanded ? null : String(order.id))}
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
                            <div style={{ marginTop: 8 }}>
                              <OrderTagEditor
                                orderId={order.id}
                                currentTags={order.tags}
                                availableTags={availableTags}
                                draftTagsByOrder={draftTagsByOrder}
                                setDraftTagsByOrder={setDraftTagsByOrder}
                                onAdd={handleOrderTagAdd}
                                onRemove={handleOrderTagRemove}
                                saving={!!tagSavingByOrder[String(order.id || '')]}
                                error={tagErrorByOrder[String(order.id || '')]}
                              />
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
                                      onChangeStatus={(nextStatus) => handleProductionStatusChange(item.sku, item.production_status, nextStatus)}
                                    />
                                  </div>
                                  <ProductionNotesInput
                                    initialValue={item.notes}
                                    status={item.production_status}
                                    onChangeNotes={(notes) => handleProductionNotesChange(item.sku, item.production_status, notes)}
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
                      <th style={{ textAlign: 'left', padding: '12px 12px', fontWeight: 700, color: '#64748b', fontSize: 12, textTransform: 'uppercase', letterSpacing: '.3px' }}>Tags</th>
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
                        <tr onClick={() => setExpandedOrderId(isExpandedMatch(expandedOrderId, order.id) ? null : String(order.id))}
                          style={{ cursor: 'pointer', borderBottom: '1px solid #f1f5f9', transition: 'background .1s',
                            background: isExpandedMatch(expandedOrderId, order.id) ? '#f8fafc' : '#fff' }}
                          onMouseEnter={e => { if (!isExpandedMatch(expandedOrderId, order.id)) e.currentTarget.style.background = '#fafafa'; }}
                          onMouseLeave={e => { if (!isExpandedMatch(expandedOrderId, order.id)) e.currentTarget.style.background = '#fff'; }}>
                          <td style={{ textAlign: 'center', padding: '10px 8px', color: '#cbd5e1' }}>
                            {itens.length > 0 && <ChevronIcon isExpanded={isExpandedMatch(expandedOrderId, order.id)} />}
                          </td>
                          <td style={{ padding: '10px 12px', fontWeight: 700, color: '#0f172a' }}>{order.numero ?? order.id}</td>
                          <td style={{ padding: '10px 12px', color: '#64748b' }}>{order.numeroLoja || '—'}</td>
                          <td style={{ padding: '10px 12px', color: '#475569' }}>{order.data ? new Date(order.data).toLocaleDateString('pt-BR') : '—'}</td>
                          <td style={{ padding: '10px 12px', color: '#334155', maxWidth: 200, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{order.cliente}</td>
                          <td style={{ padding: '10px 12px', textAlign: 'center' }}><StatusBadge text={order.situacao} /></td>
                          <td style={{ padding: '10px 12px', textAlign: 'center', fontSize: 12, color: '#64748b' }}>{order.production_summary || '—'}</td>
                          <td style={{ padding: '10px 12px', minWidth: 240 }}>
                            <OrderTagEditor
                              orderId={order.id}
                              currentTags={order.tags}
                              availableTags={availableTags}
                              draftTagsByOrder={draftTagsByOrder}
                              setDraftTagsByOrder={setDraftTagsByOrder}
                              onAdd={handleOrderTagAdd}
                              onRemove={handleOrderTagRemove}
                              saving={!!tagSavingByOrder[String(order.id || '')]}
                              error={tagErrorByOrder[String(order.id || '')]}
                            />
                          </td>
                          <td style={{ padding: '10px 4px', fontSize: 14, textAlign: 'center' }} title={order.has_frete ? 'Envio' : 'Retirada'}>{order.has_frete ? '🚚' : '🏪'}</td>
                          <td style={{ padding: '10px 12px', textAlign: 'right', fontWeight: 700, color: '#0f172a' }}>{formatBRL(order.total)}</td>
                        </tr>
                        {isExpandedMatch(expandedOrderId, order.id) && itens.length > 0 && (
                          <tr>
                            <td colSpan="10" style={{ padding: 0 }}>
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
                                            onChangeStatus={(nextStatus) => handleProductionStatusChange(item.sku, item.production_status, nextStatus)}
                                          />
                                        </td>
                                        <td style={{ textAlign: 'right', padding: '7px 8px', color: '#64748b' }}>{item.quantity}</td>
                                        <td style={{ textAlign: 'right', padding: '7px 8px', fontWeight: 600, color: '#0f172a' }}>{formatBRL(item.paid_total ?? item.total)}</td>
                                        <td style={{ padding: '7px 8px', minWidth: 150 }}>
                                          <ProductionNotesInput
                                            initialValue={item.notes}
                                            status={item.production_status}
                                            onChangeNotes={(notes) => handleProductionNotesChange(item.sku, item.production_status, notes)}
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
