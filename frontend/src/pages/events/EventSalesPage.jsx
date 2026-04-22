import React, { useEffect, useMemo, useState, useCallback, useRef } from 'react';
import * as XLSX from 'xlsx';
import { Layout } from '../../components/Layout';
import { ProductionStatusBadge, ProductionNotesInput } from '../../components/ProductionControls';
import useIsMobile from '../../hooks/useIsMobile';
import { useVersionPolling } from '../../hooks/useVersionPolling';
import { normalizeProductionStatus, deriveOrderStatusFromItems, countFinalizedItems, isFinalProductionStatus } from '../../utils/orderStatus.js';

const API_BASE = '/api';
const EVENT_SALES_UI_STATE_KEY = 'smartbling:event-sales:ui-state:v2';

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

function readSavedUiState() {
  if (typeof window === 'undefined') return null;
  try {
    const raw = window.localStorage.getItem(EVENT_SALES_UI_STATE_KEY);
    if (!raw) return null;
    const parsed = JSON.parse(raw);
    return {
      selectedEventId: parsed?.selectedEventId ? String(parsed.selectedEventId) : '',
      groupBy: parsed?.groupBy === 'item' ? 'item' : 'pedido',
      expandedOrderId: normalizeExpandedKey(parsed?.expandedOrderId),
      searchTerm: typeof parsed?.searchTerm === 'string' ? parsed.searchTerm : '',
      skuTerm: typeof parsed?.skuTerm === 'string' ? parsed.skuTerm : '',
      selectedStatuses: Array.isArray(parsed?.selectedStatuses)
        ? new Set(parsed.selectedStatuses.filter((value) => typeof value === 'string' && value.trim()))
        : null,
      scrollY: Number.isFinite(Number(parsed?.scrollY)) ? Math.max(0, Number(parsed.scrollY)) : 0,
    };
  } catch {
    return null;
  }
}

function persistUiState(state) {
  if (typeof window === 'undefined') return;
  try {
    window.localStorage.setItem(EVENT_SALES_UI_STATE_KEY, JSON.stringify({
      selectedEventId: state.selectedEventId || '',
      groupBy: state.groupBy === 'item' ? 'item' : 'pedido',
      expandedOrderId: state.expandedOrderId ?? null,
      searchTerm: state.searchTerm || '',
      skuTerm: state.skuTerm || '',
      selectedStatuses: state.selectedStatuses ? Array.from(state.selectedStatuses) : null,
      scrollY: Number.isFinite(Number(state.scrollY)) ? Math.max(0, Number(state.scrollY)) : 0,
    }));
  } catch {
    // Ignore persistence failures (private mode/quota).
  }
}

function formatBRL(value) {
  return new Intl.NumberFormat('pt-BR', { style: 'currency', currency: 'BRL' }).format(value ?? 0);
}

function formatDate(value) {
  if (!value) return '—';
  return new Date(value).toLocaleDateString('pt-BR');
}

function toCsvCell(value, delimiter) {
  const normalized = value == null ? '' : String(value);
  const escaped = normalized.replace(/"/g, '""');
  const needsQuotes = escaped.includes('"') || escaped.includes('\n') || escaped.includes('\r') || escaped.includes(delimiter);
  return needsQuotes ? `"${escaped}"` : escaped;
}

function slugifyText(value) {
  return String(value || '')
    .normalize('NFD')
    .replace(/[\u0300-\u036f]/g, '')
    .replace(/[^a-zA-Z0-9]+/g, '-')
    .replace(/^-+|-+$/g, '')
    .toLowerCase();
}

function escapeHtml(text) {
  return String(text ?? '')
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#39;');
}

function getOrderTagLabel(order) {
  const tags = Array.isArray(order?.tags)
    ? order.tags.filter((tag) => (tag || '').toString().trim())
    : [];
  if (tags.length > 0) return tags.join(', ');
  const fallback = String(order?.tag || '').trim();
  return fallback || '';
}

function buildLabelsFromCampaignOrders(orders) {
  const labels = [];
  for (const order of orders || []) {
    const blingNumber = String(order?.numero ?? order?.id ?? '—');
    const nuvemshopNumber = String(order?.numero_loja || '—');
    const buyerName = String(order?.cliente || '—').trim() || '—';
    const tagLabel = getOrderTagLabel(order);
    const items = Array.isArray(order?.matched_items) ? order.matched_items : [];

    for (const item of items) {
      labels.push({
        orderCode: `${blingNumber}/${nuvemshopNumber}`,
        buyerName,
        tagLabel,
        itemName: String(item?.product_name || '—').trim() || '—',
        quantity: Number.isFinite(Number(item?.quantity)) ? Number(item.quantity) : 0,
        sku: String(item?.sku || '').trim(),
        notes: String(item?.notes || '').trim(),
      });
    }
  }
  return labels;
}

function buildBatchLabelsPrintHtml(labels) {
  const labelsHtml = labels.map((label) => {
    const notesText = label.notes || 'Sem observações';
    const qtyText = `Qtd: ${label.quantity > 0 ? label.quantity : '—'}`;
    const skuText = label.sku ? `SKU: ${label.sku}` : '';

    return `
      <section class="label-sheet">
        <div class="label">
          <div class="order-panel">
            <div class="order-caption">PEDIDO:</div>
            <div class="order-code">${escapeHtml(label.orderCode)}</div>
          </div>

          <div class="solid-divider"></div>

          <div class="client-block">
            <div class="client-title">NOME DO CLIENTE:</div>
            <div class="client-name">${escapeHtml(label.buyerName)}</div>
            ${label.tagLabel ? `<div class="client-tag">TAG: ${escapeHtml(label.tagLabel)}</div>` : ''}
          </div>

          <div class="dotted-divider"></div>

          <div class="bottom-grid">
            <div class="item-block">
              <div class="section-title">ITEM COMPRADO:</div>
              <div class="item-name">${escapeHtml(label.itemName)}</div>
              <div class="item-meta">
                <div class="meta-line">${escapeHtml(qtyText)}</div>
                ${skuText ? `<div class="meta-line">${escapeHtml(skuText)}</div>` : ''}
              </div>
            </div>
            <div class="notes-block">
              <div class="section-title">NOTAS:</div>
              <div class="notes-text">${escapeHtml(notesText)}</div>
            </div>
          </div>
        </div>
      </section>`;
  }).join('');

  return `<!doctype html>
<html>
  <head>
    <meta charset="utf-8" />
    <title>Etiquetas de pedidos</title>
    <style>
      @page {
        size: 100mm 50mm;
        margin: 0 0 5mm 0;
      }

      html, body {
        margin: 0;
        padding: 0;
        background: #fff;
        font-family: Arial, sans-serif;
      }

      .label-sheet {
        width: 100mm;
        height: 50mm;
        page-break-after: always;
        box-sizing: border-box;
      }

      .label {
        width: 100mm;
        height: 50mm;
        box-sizing: border-box;
        border: none;
        padding: 3mm 3.5mm 2.5mm;
        display: flex;
        flex-direction: column;
      }

      .order-panel {
        background: #000;
        color: #fff;
        border-radius: 2mm;
        padding: 1.2mm 2mm 1.4mm;
        flex-shrink: 0;
      }

      .order-caption {
        font-size: 2.5mm;
        font-weight: 800;
        letter-spacing: 0.1mm;
      }

      .order-code {
        margin-top: 0.3mm;
        font-size: 7mm;
        line-height: 1;
        font-weight: 800;
      }

      .solid-divider {
        border-top: 0.6mm solid #000;
        margin: 1.2mm 0 1mm;
        flex-shrink: 0;
      }

      .client-block {
        flex-shrink: 0;
      }

      .client-title {
        font-size: 2.3mm;
        font-weight: 800;
        line-height: 1;
      }

      .client-name {
        margin-top: 0.5mm;
        font-size: 5.5mm;
        font-weight: 800;
        line-height: 1.1;
        white-space: nowrap;
        overflow: hidden;
        text-overflow: ellipsis;
      }

      .client-tag {
        margin-top: 0.5mm;
        font-size: 2.2mm;
        font-weight: 700;
      }

      .dotted-divider {
        border-top: 0.6mm dotted #000;
        margin: 1mm 0 0.8mm;
        flex-shrink: 0;
      }

      .bottom-grid {
        flex: 1;
        display: grid;
        grid-template-columns: 62% 38%;
        gap: 1.5mm;
        min-height: 0;
        overflow: hidden;
      }

      .item-block,
      .notes-block {
        min-width: 0;
        overflow: hidden;
      }

      .item-block {
        display: flex;
        flex-direction: column;
        min-height: 0;
      }

      .notes-block {
        border-left: 0.6mm solid #000;
        padding-left: 1.5mm;
      }

      .section-title {
        font-size: 2.2mm;
        font-weight: 800;
        margin-bottom: 0.2mm;
        line-height: 1.1;
      }

      .item-name {
        font-size: 2.8mm;
        font-weight: 800;
        line-height: 1.1;
        word-break: break-word;
        overflow-wrap: anywhere;
        white-space: normal;
        flex: 1;
        min-height: 0;
        overflow: hidden;
      }

      .item-meta {
        margin-top: 0.6mm;
        font-size: 1.95mm;
        font-weight: 600;
        line-height: 1.2;
        white-space: normal;
        overflow: hidden;
        flex-shrink: 0;
      }

      .meta-line {
        word-break: break-word;
        overflow-wrap: anywhere;
      }

      .notes-text {
        margin-top: 0.8mm;
        font-size: 2.4mm;
        font-weight: 600;
        line-height: 1.3;
        word-break: break-word;
        overflow-wrap: break-word;
        white-space: normal;
        overflow: hidden;
      }
    </style>
  </head>
  <body>
    ${labelsHtml}
    <script>
      function fitItemNameText() {
        var itemEls = document.querySelectorAll('.item-name');
        itemEls.forEach(function (el) {
          var computed = window.getComputedStyle(el);
          var currentPx = parseFloat(computed.fontSize) || 12;
          var minPx = 6;

          while (el.scrollHeight > el.clientHeight + 0.5 && currentPx > minPx) {
            currentPx -= 0.25;
            el.style.fontSize = currentPx + 'px';
          }
        });
      }

      window.onload = function () {
        fitItemNameText();
        window.focus();
        window.print();
      };
    </script>
  </body>
</html>`;
}

function downloadCsvFile(filename, content) {
  const blob = new Blob([`\uFEFF${content}`], { type: 'text/csv;charset=utf-8;' });
  const url = window.URL.createObjectURL(blob);
  const anchor = document.createElement('a');
  anchor.href = url;
  anchor.download = filename;
  document.body.appendChild(anchor);
  anchor.click();
  document.body.removeChild(anchor);
  window.URL.revokeObjectURL(url);
}

function downloadXlsxFile(filename, headers, rows) {
  const worksheetRows = [headers, ...rows.map((row) => headers.map((header) => row[header] ?? ''))];
  const worksheet = XLSX.utils.aoa_to_sheet(worksheetRows);
  const workbook = XLSX.utils.book_new();
  XLSX.utils.book_append_sheet(workbook, worksheet, 'Pedidos');
  XLSX.writeFile(workbook, filename);
}

function StatusBadge({ text }) {
  const lower = (text || '').toLowerCase();
  let cls = 'badge badge--yellow';
  if (lower.includes('atendido') || lower.includes('entregue')) cls = 'badge badge--green';
  else if (lower.includes('imped')) cls = 'badge badge--red';
  else if (lower.includes('pronto')) cls = 'badge badge--purple';
  else if (lower.includes('andamento') || lower.includes('produ')) cls = 'badge badge--blue';
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
  if (lower.includes('imped')) return 'Impedido';
  if (lower.includes('parcial') && lower.includes('entreg')) return 'Parcialmente entregue';
  if (lower.includes('pronto') && lower.includes('envio')) return 'Pronto para envio';
  if (lower.includes('pronto') && lower.includes('retirada')) return 'Pronto para retirada';
  if (lower.includes('andamento')) return 'Em andamento';
  if (lower.includes('cancel') || lower.includes('devolv')) return 'Cancelado';
  if (lower.includes('atendido') || lower.includes('conclu') || lower.includes('entreg')) return 'Atendido';
  return 'Em aberto';
}

/**
 * Maps canonical production status key (from shared util) to EventSalesPage's
 * legacy UI keys used for item status chips/summary.
 */
function normalizeProductionStatusKey(value) {
  const key = normalizeProductionStatus(value);
  if (key === 'impedimento') return 'blocked';
  if (key === 'entregue') return 'delivered';
  if (key === 'embalado') return 'packed';
  // EventSalesPage distinguishes 'Produzido' from 'Em produção'
  if ((value || '').toString().trim().toLowerCase().includes('produz')) return 'produced';
  if (key === 'em_producao') return 'inProduction';
  return 'pending';
}

function EventOrderTagEditor({
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
  const datalistId = `event-tags-${key || 'unknown'}`;
  const value = key ? (draftTagsByOrder[key] ?? '') : '';
  const tags = Array.isArray(currentTags) ? currentTags.filter(Boolean) : [];

  return (
    <div onClick={(e) => e.stopPropagation()} style={{ display: 'grid', gap: 4 }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 6, flexWrap: 'wrap' }}>
        <input
          id={`event-order-tag-input-${key || 'unknown'}`}
          name="eventOrderTagInput"
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
        <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
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
        </div>
      )}
      <div style={{ fontSize: 11, color: '#94a3b8' }}>Pressione Enter para adicionar.</div>
      {!!error && <span style={{ fontSize: 11, color: '#b91c1c' }}>{error}</span>}
    </div>
  );
}

export function EventSalesPage() {
  console.log('[EventSalesPage] Component rendering');
  const savedUiState = readSavedUiState();
  const isMobile = useIsMobile(1024);
  const [events, setEvents] = useState([]);
  const [selectedEventId, setSelectedEventId] = useState(savedUiState?.selectedEventId || '');
  const [salesData, setSalesData] = useState(null);
  const [loadingEvents, setLoadingEvents] = useState(false);
  const [loadingSales, setLoadingSales] = useState(false);
  const [loadingExport, setLoadingExport] = useState(false);
  const [loadingPrint, setLoadingPrint] = useState(false);
  const [exportMenuOpen, setExportMenuOpen] = useState(false);
  const [eventOrdersCount, setEventOrdersCount] = useState({});
  const [error, setError] = useState(null);
  const [searchTerm, setSearchTerm] = useState(savedUiState?.searchTerm || '');
  const [skuTerm, setSkuTerm] = useState(savedUiState?.skuTerm || '');
  const [selectedStatuses, setSelectedStatuses] = useState(() => savedUiState?.selectedStatuses ?? null);
  const [expandedOrderId, setExpandedOrderId] = useState(savedUiState?.expandedOrderId || null);
  const [groupBy, setGroupBy] = useState(savedUiState?.groupBy || 'pedido');
  const [selectedItemStatusFilter, setSelectedItemStatusFilter] = useState(null);
  const [availableTags, setAvailableTags] = useState([]);
  const [selectedTagFilter, setSelectedTagFilter] = useState('');
  const [draftTagsByOrder, setDraftTagsByOrder] = useState({});
  const [tagSavingByOrder, setTagSavingByOrder] = useState({});
  const [tagErrorByOrder, setTagErrorByOrder] = useState({});
  const [statusFeedbackByItem, setStatusFeedbackByItem] = useState({});
  const deltaCursorRef = useRef(null);
  const salesInFlightRef = useRef(new Set());
  const suppressDeltaUntilRef = useRef(0);
  const initialScrollYRef = useRef(savedUiState?.scrollY || 0);
  const hasRestoredScrollRef = useRef(false);

  const itemFeedbackKey = useCallback((sku, orderId) => {
    const normalizedSku = String(sku || '').trim().toUpperCase();
    const normalizedOrderId = String(orderId || '').trim();
    return `${normalizedOrderId}::${normalizedSku}`;
  }, []);

  const setItemFeedback = useCallback((sku, orderId, feedback) => {
    const key = itemFeedbackKey(sku, orderId);
    setStatusFeedbackByItem((prev) => ({ ...prev, [key]: feedback }));
  }, [itemFeedbackKey]);

  const clearItemFeedbackLater = useCallback((sku, orderId, delayMs = 1500) => {
    const key = itemFeedbackKey(sku, orderId);
    window.setTimeout(() => {
      setStatusFeedbackByItem((prev) => {
        if (!prev[key]) return prev;
        const next = { ...prev };
        delete next[key];
        return next;
      });
    }, delayMs);
  }, [itemFeedbackKey]);

  const markLocalMutation = useCallback(() => {
    suppressDeltaUntilRef.current = Date.now() + 4000;
  }, []);

  const includeStatusInFilter = useCallback((statusLabel) => {
    const normalized = normalizeStatusLabel(statusLabel);
    if (!normalized) return;
    setSelectedStatuses((prev) => {
      if (prev === null) return prev;
      if (prev.has(normalized)) return prev;
      const next = new Set(prev);
      next.add(normalized);
      return next;
    });
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
        const finalizedCount = countFinalizedItems(items);
        const nextSituacao = deriveOrderStatusFromItems(items, !!order.has_frete);
        includeStatusInFilter(nextSituacao);
        return {
          ...order,
          situacao: nextSituacao,
          matched_items: items,
          production_summary: `${finalizedCount}/${items.length} Finalizado`,
        };
      });
      return { ...prev, orders };
    });
  }, [includeStatusInFilter]);

  const handleProductionStatusChange = useCallback(async (sku, orderId, currentStatus, nextStatus) => {
    if (nextStatus === currentStatus) return;
    try {
      setItemFeedback(sku, orderId, 'saving');
      const resp = await fetch(`${API_BASE}/events/${selectedEventId}/items/${encodeURIComponent(sku)}/production`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ production_status: nextStatus, bling_order_id: orderId || null }),
      });
      if (!resp.ok) {
        const data = await resp.json().catch(() => ({}));
        throw new Error(data.detail || 'Falha ao salvar status de produção');
      }
      markLocalMutation();
      handleProductionSaved(sku, nextStatus, undefined, orderId);
      setItemFeedback(sku, orderId, 'success');
      clearItemFeedbackLater(sku, orderId);
    } catch (err) {
      console.error('Failed to save production status', err);
      setItemFeedback(sku, orderId, 'error');
      clearItemFeedbackLater(sku, orderId, 2500);
    }
  }, [clearItemFeedbackLater, handleProductionSaved, markLocalMutation, selectedEventId, setItemFeedback]);

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
      const targetOrder = salesData?.orders?.find((order) => String(order.id) === String(orderId));
      const matchedItems = Array.isArray(targetOrder?.matched_items) ? targetOrder.matched_items : [];

      if (newStatus === 'Atendido' && matchedItems.length > 0) {
        const itemUpdates = matchedItems.map((item) =>
          fetch(`${API_BASE}/events/${selectedEventId}/items/${encodeURIComponent(item.sku)}/production`, {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
              production_status: 'Entregue',
              bling_order_id: orderId || null,
            }),
          }).then((resp) => {
            if (!resp.ok) {
              return resp.json().catch(() => ({})).then((data) => {
                throw new Error((data.detail || `Falha ao atualizar item ${item.sku || ''}`).trim());
              });
            }
            return resp;
          })
        );
        await Promise.all(itemUpdates);
      }

      const resp = await fetch(`${API_BASE}/events/${selectedEventId}/orders/${orderId}/status`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ situacao: newStatus }),
      });
      if (!resp.ok) {
        const data = await resp.json().catch(() => ({}));
        throw new Error(data.detail || 'Falha ao atualizar status');
      }
      markLocalMutation();
      includeStatusInFilter(newStatus);
      setSalesData((prev) => {
        if (!prev) return prev;
        const orders = prev.orders.map((o) => {
          if (o.id !== orderId) return o;
          const nextItems = Array.isArray(o.matched_items)
            ? o.matched_items.map((item) => (
                newStatus === 'Atendido'
                  ? { ...item, production_status: 'Entregue' }
                  : item
              ))
            : o.matched_items;
          const finalizedCount = countFinalizedItems(nextItems);
          return {
            ...o,
            situacao: newStatus,
            matched_items: nextItems,
            production_summary: `${finalizedCount}/${nextItems?.length || 0} Finalizado`,
          };
        });
        return { ...prev, orders };
      });
    } catch (err) {
      alert(`Erro: ${err.message}`);
    }
  }, [includeStatusInFilter, markLocalMutation, salesData, selectedEventId]);

  const loadEventTags = useCallback(async (eventId) => {
    if (!eventId) {
      setAvailableTags([]);
      return;
    }
    try {
      const resp = await fetch(`${API_BASE}/events/${eventId}/tags`);
      if (!resp.ok) return;
      const data = await resp.json();
      setAvailableTags((data.tags || []).map((t) => t.name).filter(Boolean));
    } catch {
      // Keep page functional even if tags endpoint fails.
    }
  }, []);

  const handleOrderTagAdd = useCallback(async (orderId, rawTag) => {
    const key = String(orderId || '');
    if (!selectedEventId || !key) {
      setTagErrorByOrder((prev) => ({ ...prev, [key]: 'Pedido sem ID válido para salvar tag' }));
      return;
    }

    const chosenTag = (rawTag || '').trim();
    setTagSavingByOrder((prev) => ({ ...prev, [key]: true }));
    setTagErrorByOrder((prev) => ({ ...prev, [key]: '' }));

    try {
      if (!chosenTag) return;

      const resp = await fetch(`${API_BASE}/events/${selectedEventId}/orders/${orderId}/tag`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ tag_name: chosenTag }),
      });
      if (!resp.ok) {
        const data = await resp.json().catch(() => ({}));
        throw new Error(data.detail || 'Falha ao salvar tag');
      }
      const data = await resp.json();
      setSalesData((prev) => {
        if (!prev) return prev;
        const normalizeExisting = (order) => (Array.isArray(order.tags) ? order.tags : ((order.tag || '').trim() ? [order.tag] : []));
        return {
          ...prev,
          orders: (prev.orders || []).map((o) => {
            if (o.id !== orderId) return o;
            const existing = normalizeExisting(o);
            const resolvedTags = Array.isArray(data.tags)
              ? data.tags
              : ((data.tag || '').trim() ? Array.from(new Set([...existing, String(data.tag).trim()])) : Array.from(new Set([...existing, chosenTag])));
            return { ...o, tags: resolvedTags, tag: resolvedTags[0] || null };
          }),
        };
      });
      setAvailableTags((prev) => {
        const next = new Set(prev);
        if (Array.isArray(data.tags)) {
          data.tags.forEach((name) => next.add(name));
        } else {
          next.add(chosenTag);
        }
        return Array.from(next).sort((a, b) => a.localeCompare(b, 'pt-BR'));
      });
      setDraftTagsByOrder((prev) => ({ ...prev, [key]: '' }));
      markLocalMutation();
    } catch (err) {
      setTagErrorByOrder((prev) => ({ ...prev, [key]: err.message || 'Erro ao salvar tag' }));
    } finally {
      setTagSavingByOrder((prev) => ({ ...prev, [key]: false }));
    }
  }, [markLocalMutation, selectedEventId]);

  const handleOrderTagRemove = useCallback(async (orderId, tagName) => {
    const key = String(orderId || '');
    if (!selectedEventId || !key || !(tagName || '').trim()) return;

    setTagSavingByOrder((prev) => ({ ...prev, [key]: true }));
    setTagErrorByOrder((prev) => ({ ...prev, [key]: '' }));

    try {
      const params = new URLSearchParams({ tag_name: tagName });
      const resp = await fetch(`${API_BASE}/events/${selectedEventId}/orders/${orderId}/tag?${params.toString()}`, { method: 'DELETE' });
      if (!resp.ok) {
        const data = await resp.json().catch(() => ({}));
        throw new Error(data.detail || 'Falha ao remover tag');
      }
      const data = await resp.json();
      setSalesData((prev) => {
        if (!prev) return prev;
        const normalizeExisting = (order) => (Array.isArray(order.tags) ? order.tags : ((order.tag || '').trim() ? [order.tag] : []));
        return {
          ...prev,
          orders: (prev.orders || []).map((o) => {
            if (o.id !== orderId) return o;
            const existing = normalizeExisting(o);
            const resolvedTags = Array.isArray(data.tags)
              ? data.tags
              : existing.filter((name) => (name || '').trim().toLowerCase() !== (tagName || '').trim().toLowerCase());
            return { ...o, tags: resolvedTags, tag: resolvedTags[0] || null };
          }),
        };
      });
      await loadEventTags(selectedEventId);
      markLocalMutation();
    } catch (err) {
      setTagErrorByOrder((prev) => ({ ...prev, [key]: err.message || 'Erro ao remover tag' }));
    } finally {
      setTagSavingByOrder((prev) => ({ ...prev, [key]: false }));
    }
  }, [loadEventTags, markLocalMutation, selectedEventId]);

  async function loadEvents() {
    try {
      setLoadingEvents(true);
      setError(null);
      console.log('[EventSalesPage] loadEvents: fetching /api/events');
      const resp = await fetch(`${API_BASE}/events`);
      console.log('[EventSalesPage] loadEvents: response status', resp.status);
      if (!resp.ok) {
        const errData = await resp.json().catch(() => ({}));
        throw new Error(errData.detail || 'Falha ao carregar campanhas');
      }
      const data = await resp.json();
      const list = Array.isArray(data) ? data : [];
      const activeList = list.filter((event) => event.is_active !== false);
      console.log('[EventSalesPage] loadEvents: got', list.length, 'events,', activeList.length, 'active');
      setEvents(activeList);
      if (!selectedEventId && activeList.length > 0) {
        setSelectedEventId(String(activeList[0].id));
      }
    } catch (err) {
      console.error('[EventSalesPage] loadEvents error:', err);
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

    const requestKey = String(eventId);
    if (salesInFlightRef.current.has(requestKey)) {
      return;
    }
    salesInFlightRef.current.add(requestKey);

    try {
      setLoadingSales(true);
      setError(null);
      const query = '';
      console.log('[EventSalesPage] loadSales: fetching /api/events/' + eventId + '/sales' + query);
      const resp = await fetch(`${API_BASE}/events/${eventId}/sales${query}`);
      console.log('[EventSalesPage] loadSales: response status', resp.status);
      if (!resp.ok) {
        const errData = await resp.json().catch(() => ({}));
        const message = errData.detail || 'Falha ao carregar pedidos da campanha';
        throw new Error(message);
      }
      const salesJson = await resp.json();
      console.log('[EventSalesPage] loadSales: got', salesJson?.summary?.orders_count, 'orders');
      setSalesData(salesJson);
      setEventOrdersCount((prev) => ({
        ...prev,
        [String(eventId)]: Number(salesJson?.summary?.orders_count || 0),
      }));
      deltaCursorRef.current = new Date().toISOString();
    } catch (err) {
      setError(err.message);
      setSalesData(null);
    } finally {
      salesInFlightRef.current.delete(requestKey);
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

      (delta.order_status_updates || []).forEach((update) => {
        includeStatusInFilter(update?.situacao);
      });
      const productionByExactKey = new Map();
      const productionBySku = new Map();
      productionUpdates.forEach((u) => {
        const sku = (u.sku || '').toUpperCase();
        if (!sku) return;
        if (u.bling_order_id == null) {
          // Keep only latest update per SKU (last write wins).
          productionBySku.set(sku, u);
          return;
        }
        const exactKey = `${sku}::${Number(u.bling_order_id)}`;
        // Keep only latest update per SKU+order (last write wins).
        productionByExactKey.set(exactKey, u);
      });

      setSalesData((prev) => {
        if (!prev) return prev;
        const orders = (prev.orders || []).map((order) => {
          const orderId = Number(order.id);
          const nextStatus = statusMap.get(orderId);
          const matchedItems = (order.matched_items || []).map((item) => {
            const sku = (item.sku || '').toUpperCase();
            const exactKey = `${sku}::${orderId}`;
            // Prefer strict SKU+order match, fallback to SKU-only update.
            const match = productionByExactKey.get(exactKey) || productionBySku.get(sku);
            if (!match) return item;
            return {
              ...item,
              production_status: match.production_status,
              notes: match.notes,
            };
          });
          const embalado = countFinalizedItems(matchedItems);
          return {
            ...order,
            ...(nextStatus ? { situacao: nextStatus } : {}),
            matched_items: matchedItems,
            production_summary: `${embalado}/${matchedItems.length} Finalizado`,
          };
        });
        return { ...prev, orders };
      });
    } catch {
      // Keep current list stable; retry on next polling cycle.
    }
  }, [includeStatusInFilter, selectedEventId]);

  useEffect(() => {
    loadEvents();
  }, []);

  useEffect(() => {
    if (loadingEvents) return;
    if (events.length === 0) {
      setSalesData(null);
      return;
    }
    const hasSelected = events.some((event) => String(event.id) === String(selectedEventId));
    if (!hasSelected) {
      setSelectedEventId(String(events[0].id));
    }
  }, [events, loadingEvents, selectedEventId]);

  useEffect(() => {
    persistUiState({
      selectedEventId,
      groupBy,
      expandedOrderId,
      searchTerm,
      skuTerm,
      selectedStatuses,
      scrollY: getCurrentScrollY(),
    });
  }, [selectedEventId, groupBy, expandedOrderId, searchTerm, skuTerm, selectedStatuses]);

  useEffect(() => {
    if (typeof window === 'undefined') return undefined;
    const persistOnUnload = () => {
      persistUiState({
        selectedEventId,
        groupBy,
        expandedOrderId,
        searchTerm,
        skuTerm,
        selectedStatuses,
        scrollY: getCurrentScrollY(),
      });
    };
    window.addEventListener('beforeunload', persistOnUnload);
    return () => window.removeEventListener('beforeunload', persistOnUnload);
  }, [selectedEventId, groupBy, expandedOrderId, searchTerm, skuTerm, selectedStatuses]);

  useEffect(() => {
    if (selectedEventId) {
      loadSales(selectedEventId);
      loadEventTags(selectedEventId);
    }
  }, [loadEventTags, loadSales, selectedEventId]);

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
    const statusSet = new Set(['Em aberto', 'Cancelado']);
    allOrders.forEach((order) => statusSet.add(normalizeStatusLabel(order.situacao)));
    return [...statusSet].sort();
  }, [salesData]);

  useEffect(() => {
    if (availableStatuses.length > 0) {
      setSelectedStatuses((prev) => {
        if (prev === null) return new Set(availableStatuses);
        const allowed = new Set(availableStatuses);
        const filtered = new Set(Array.from(prev).filter((status) => allowed.has(status)));
        return filtered;
      });
    }
  }, [availableStatuses]);

  useEffect(() => {
    if (loadingSales || hasRestoredScrollRef.current || typeof window === 'undefined') return;
    hasRestoredScrollRef.current = true;
    if (initialScrollYRef.current > 0) {
      window.requestAnimationFrame(() => {
        restoreScrollY(initialScrollYRef.current);
      });
    }
  }, [loadingSales]);

  const visibleOrders = useMemo(() => {
    const allOrders = Array.isArray(salesData?.orders) ? salesData.orders : [];
    const term = (searchTerm || '').trim().toLowerCase();
    const activeStatuses = selectedStatuses || new Set();
    const wantedTag = (selectedTagFilter || '').trim().toLowerCase();

    return allOrders.filter((order) => {
      const statusLabel = normalizeStatusLabel(order.situacao);
      const statusOk = activeStatuses.has(statusLabel);
      if (!statusOk) return false;

      if (wantedTag) {
        const orderTags = Array.isArray(order.tags)
          ? order.tags.map((name) => (name || '').toString().trim().toLowerCase())
          : ((order.tag || '').toString().trim() ? [(order.tag || '').toString().trim().toLowerCase()] : []);
        if (!orderTags.includes(wantedTag)) return false;
      }

      if (!term) return true;

      const pedidoText = String(order.numero || order.id || '').toLowerCase();
      const nuvemshopText = String(order.numero_loja || order.numeroLoja || '').toLowerCase();
      const clienteText = String(order.cliente || '').toLowerCase();
      return pedidoText.includes(term) || nuvemshopText.includes(term) || clienteText.includes(term);
    });
  }, [salesData, searchTerm, selectedStatuses, selectedTagFilter]);

  const filteredOrdersByItemStatus = useMemo(() => {
    const normalizedSkuTerm = (skuTerm || '').trim().toLowerCase();

    return visibleOrders
      .map((order) => {
        const items = Array.isArray(order.matched_items) ? order.matched_items : [];
        const skuFilteredItems = normalizedSkuTerm
          ? items.filter((item) => {
              const skuText = String(item?.sku || '').toLowerCase();
              const productText = String(item?.product_name || '').toLowerCase();
              return skuText.includes(normalizedSkuTerm) || productText.includes(normalizedSkuTerm);
            })
          : items;

        const filteredItems = selectedItemStatusFilter
          ? skuFilteredItems.filter(
              (item) => normalizeProductionStatusKey(item.production_status) === selectedItemStatusFilter,
            )
          : skuFilteredItems;

        if (filteredItems.length === 0) return null;
        const totalMatched = filteredItems.reduce((acc, item) => acc + Number(item.paid_total || 0), 0);
        const packedCount = countFinalizedItems(filteredItems);
        return {
          ...order,
          matched_items: filteredItems,
          total_matched: totalMatched,
          production_summary: `${packedCount}/${filteredItems.length} Finalizado`,
        };
      })
      .filter(Boolean);
  }, [visibleOrders, selectedItemStatusFilter, skuTerm]);

  const filteredSummary = useMemo(() => {
    const matchedItemsCount = filteredOrdersByItemStatus.reduce((acc, order) => acc + (order.matched_items?.length || 0), 0);
    const totalMatched = filteredOrdersByItemStatus.reduce((acc, order) => acc + (order.total_matched || 0), 0);
    return {
      orders_count: filteredOrdersByItemStatus.length,
      matched_items_count: matchedItemsCount,
      total_matched: totalMatched,
    };
  }, [filteredOrdersByItemStatus]);

  const productionProgressPct = useMemo(() => {
    const totalItems = filteredSummary.matched_items_count || 0;
    if (!totalItems) return 0;

    const producedOrPackedCount = filteredOrdersByItemStatus.reduce((acc, order) => {
      const items = Array.isArray(order.matched_items) ? order.matched_items : [];
      const count = items.filter((item) => {
        const key = normalizeProductionStatusKey(item.production_status);
        return key === 'produced' || key === 'packed' || key === 'delivered';
      }).length;
      return acc + count;
    }, 0);

    return Math.round((producedOrPackedCount / totalItems) * 100);
  }, [filteredSummary.matched_items_count, filteredOrdersByItemStatus]);

  const itemStatusSummary = useMemo(() => {
    const summary = {
      pending: 0,
      inProduction: 0,
      produced: 0,
      packed: 0,
      delivered: 0,
      blocked: 0,
    };

    visibleOrders.forEach((order) => {
      const items = Array.isArray(order.matched_items) ? order.matched_items : [];
      items.forEach((item) => {
        const key = normalizeProductionStatusKey(item.production_status);
        if (key === 'blocked') {
          summary.blocked += 1;
        } else if (key === 'delivered') {
          summary.delivered += 1;
        } else if (key === 'packed') {
          summary.packed += 1;
        } else if (key === 'produced') {
          summary.produced += 1;
        } else if (key === 'inProduction') {
          summary.inProduction += 1;
        } else {
          summary.pending += 1;
        }
      });
    });

    return summary;
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
    const normalizedId = normalizeExpandedKey(orderId);
    setExpandedOrderId((prev) => (isExpandedMatch(prev, normalizedId) ? null : normalizedId));
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
    filteredOrdersByItemStatus.forEach((order) => {
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
          email: order.email,
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
  }, [filteredOrdersByItemStatus, groupBy]);

  const itemFilterCards = [
    { key: 'pending', label: 'Itens Pendentes', value: itemStatusSummary.pending },
    { key: 'inProduction', label: 'Itens em Produção', value: itemStatusSummary.inProduction },
    { key: 'produced', label: 'Itens Produzidos', value: itemStatusSummary.produced },
    { key: 'packed', label: 'Itens Embalados', value: itemStatusSummary.packed },
    { key: 'delivered', label: 'Itens Entregues', value: itemStatusSummary.delivered },
    { key: 'blocked', label: 'Itens com Impedimentos', value: itemStatusSummary.blocked },
  ];

  const exportCampaignOrders = useCallback(async (format = 'csv') => {
    const baseOrders = Array.isArray(filteredOrdersByItemStatus) ? filteredOrdersByItemStatus : [];
    if (baseOrders.length === 0) {
      window.alert('Não há pedidos para exportar com os filtros atuais.');
      return;
    }

    setLoadingExport(true);
    setExportMenuOpen(false);

    try {
      const orders = baseOrders;
      const currentEvent = events.find((event) => String(event.id) === String(selectedEventId));
      const eventName = currentEvent?.name || salesData?.event?.name || 'campanha';
      const delimiter = ',';

      const headers = [
      'Campanha',
      'Pedido Bling',
      'Pedido Nuvemshop',
      'Data Pedido',
      'Cliente',
      'Email Cliente',
      'Situacao Pedido',
      'Tag(s)',
      'Tipo Entrega',
      'SKU',
      'Produto',
      'Quantidade',
      'Valor Unitario Original',
      'Total Original Item',
      'Valor Unitario Pago',
      'Total Pago Item',
      'Status Producao',
      'Notas Producao',
      'Resumo Producao',
      'Total Pedido',
      'Total Itens Campanha no Pedido',
      ];

      const lines = [headers.map((header) => toCsvCell(header, delimiter)).join(delimiter)];
      const rowsForXlsx = [];

      orders.forEach((order) => {
      const items = Array.isArray(order.matched_items) ? order.matched_items : [];
      const tags = Array.isArray(order.tags)
        ? order.tags.filter(Boolean).join(' | ')
        : (order.tag || '');

        items.forEach((item) => {
        const row = {
          'Campanha': eventName,
          'Pedido Bling': order.numero || order.id || '',
          'Pedido Nuvemshop': order.numero_loja || '',
          'Data Pedido': formatDate(order.data),
          'Cliente': order.cliente || '',
          'Email Cliente': order.email || '',
          'Situacao Pedido': order.situacao || '',
          'Tag(s)': tags,
          'Tipo Entrega': order.has_frete ? 'Envio' : 'Retirada',
          'SKU': item.sku || '',
          'Produto': item.product_name || '',
          'Quantidade': item.quantity ?? 0,
          'Valor Unitario Original': item.unit_price ?? 0,
          'Total Original Item': item.total ?? 0,
          'Valor Unitario Pago': item.paid_unit_price ?? 0,
          'Total Pago Item': item.paid_total ?? 0,
          'Status Producao': item.production_status || 'Pendente',
          'Notas Producao': item.notes || '',
          'Resumo Producao': order.production_summary || '',
          'Total Pedido': order.total_order ?? 0,
          'Total Itens Campanha no Pedido': order.total_matched ?? 0,
        };
        lines.push(headers.map((header) => toCsvCell(row[header], delimiter)).join(delimiter));
        rowsForXlsx.push(row);
        });
      });

      const dateStamp = new Date().toISOString().slice(0, 19).replace(/[:T]/g, '-');
      const baseName = slugifyText(eventName) || 'campanha';
      if (format === 'xlsx') {
        const filename = `pedidos-campanha-${baseName}-${dateStamp}.xlsx`;
        downloadXlsxFile(filename, headers, rowsForXlsx);
        return;
      }
      const filename = `pedidos-campanha-${baseName}-${dateStamp}.csv`;
      downloadCsvFile(filename, lines.join('\n'));
    } finally {
      setLoadingExport(false);
    }
  }, [events, filteredOrdersByItemStatus, salesData?.event?.name, selectedEventId]);

  const printCampaignLabels = useCallback(() => {
    const baseOrders = Array.isArray(filteredOrdersByItemStatus) ? filteredOrdersByItemStatus : [];
    if (baseOrders.length === 0) {
      window.alert('Não há pedidos para imprimir com os filtros atuais.');
      return;
    }

    try {
      setLoadingPrint(true);
      const labels = buildLabelsFromCampaignOrders(baseOrders);
      if (labels.length === 0) {
        window.alert('Não há etiquetas para imprimir com os filtros atuais.');
        return;
      }

      const html = buildBatchLabelsPrintHtml(labels);
      const printWindow = window.open('', '_blank', 'width=1024,height=768');
      if (!printWindow) {
        window.alert('Não foi possível abrir a janela de impressão. Verifique o bloqueador de pop-up.');
        return;
      }

      printWindow.document.open();
      printWindow.document.write(html);
      printWindow.document.close();
    } finally {
      setExportMenuOpen(false);
      setLoadingPrint(false);
    }
  }, [filteredOrdersByItemStatus]);

  return (
    <Layout>
      <div className="page-inner">
        <div className="page-header">
          <div>
            <h2>Pedidos por Campanha</h2>
            <p className="page-subtitle">Pedidos de venda filtrados pelos produtos selecionados na campanha</p>
          </div>
          <div style={{ display: 'flex', gap: 8, alignItems: 'center', flexWrap: 'wrap' }}>
            <button className="btn-secondary" disabled={!selectedEventId || loadingSales} onClick={() => loadSales(selectedEventId)}>
              {loadingSales ? 'Atualizando...' : 'Atualizar'}
            </button>
            <div style={{ position: 'relative' }}>
              <button
                className="btn-secondary"
                disabled={!selectedEventId || loadingSales || loadingExport || loadingPrint || filteredOrdersByItemStatus.length === 0}
                onClick={() => setExportMenuOpen((prev) => !prev)}
                title="Escolha o formato para download"
              >
                {loadingExport || loadingPrint ? 'Preparando...' : 'Exportar ▾'}
              </button>
              {exportMenuOpen && !loadingExport && !loadingPrint && (
                <div
                  style={{
                    position: 'absolute',
                    right: 0,
                    top: 'calc(100% + 6px)',
                    background: '#fff',
                    border: '1px solid #e2e8f0',
                    borderRadius: 8,
                    boxShadow: '0 8px 24px rgba(0,0,0,0.12)',
                    zIndex: 30,
                    minWidth: 150,
                    overflow: 'hidden',
                  }}
                >
                  <button
                    type="button"
                    onClick={printCampaignLabels}
                    style={{
                      width: '100%',
                      textAlign: 'left',
                      padding: '10px 12px',
                      border: 'none',
                      background: '#fff',
                      color: '#0f172a',
                      fontSize: 14,
                      fontWeight: 600,
                      cursor: 'pointer',
                    }}
                  >
                    Imprimir etiquetas 10×5
                  </button>
                  <button
                    type="button"
                    onClick={() => exportCampaignOrders('csv')}
                    style={{
                      width: '100%',
                      textAlign: 'left',
                      padding: '10px 12px',
                      border: 'none',
                      borderTop: '1px solid #f1f5f9',
                      background: '#fff',
                      color: '#0f172a',
                      fontSize: 14,
                      fontWeight: 600,
                      cursor: 'pointer',
                    }}
                  >
                    Download CSV
                  </button>
                  <button
                    type="button"
                    onClick={() => exportCampaignOrders('xlsx')}
                    style={{
                      width: '100%',
                      textAlign: 'left',
                      padding: '10px 12px',
                      border: 'none',
                      borderTop: '1px solid #f1f5f9',
                      background: '#fff',
                      color: '#0f172a',
                      fontSize: 14,
                      fontWeight: 600,
                      cursor: 'pointer',
                    }}
                  >
                    Download XLSX
                  </button>
                </div>
              )}
            </div>
          </div>
        </div>

        {error && <div className="error">{error}</div>}

        <div className="card" style={{ marginBottom: 16 }}>
          <div className="card-header">
            <h3>📌 Seleção de Campanha</h3>
          </div>
          <div style={{ padding: 20 }}>
            {loadingEvents ? (
              <p className="loading">Carregando campanhas...</p>
            ) : events.length === 0 ? (
              <div className="empty-state" style={{ padding: '24px 8px' }}>
                <span className="empty-state-icon">🗂️</span>
                <p>Nenhuma campanha ativa disponível.</p>
              </div>
            ) : (
              <div style={{ display: 'grid', gap: 10 }}>
                {events.map((event) => {
                  const selected = String(selectedEventId) === String(event.id);
                  const ordersCount = eventOrdersCount[String(event.id)];
                  return (
                    <button
                      key={event.id}
                      type="button"
                      onClick={() => setSelectedEventId(String(event.id))}
                      style={{
                        border: selected ? '2px solid #2563eb' : '1px solid #e2e8f0',
                        borderRadius: 10,
                        background: selected ? '#eff6ff' : '#ffffff',
                        padding: '12px 14px',
                        textAlign: 'left',
                        cursor: 'pointer',
                        display: 'grid',
                        gap: 4,
                      }}
                    >
                      <div style={{ fontWeight: 700, color: selected ? '#1d4ed8' : '#0f172a' }}>{event.name}</div>
                      <div style={{ fontSize: 12, color: '#475569' }}>
                        {formatDate(event.start_date)} - {formatDate(event.end_date)}
                      </div>
                      <div style={{ fontSize: 12, color: '#64748b' }}>
                        {Number.isFinite(ordersCount) ? ordersCount : '...'} pedido(s)
                      </div>
                    </button>
                  );
                })}
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
                    id="event-sales-search"
                    name="eventSalesSearch"
                    type="text"
                    placeholder="Buscar por nº do pedido, nº Nuvemshop ou nome do cliente..."
                    value={searchTerm}
                    onChange={(e) => setSearchTerm(e.target.value)}
                  />
                </div>
                <div className="search-box" style={{ marginBottom: 12 }}>
                  <input
                    id="event-sales-sku-search"
                    name="eventSalesSkuSearch"
                    type="text"
                    placeholder="Filtrar por SKU ou nome do item..."
                    value={skuTerm}
                    onChange={(e) => setSkuTerm(e.target.value)}
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
                  <select
                    id="event-sales-tag-filter"
                    name="eventSalesTagFilter"
                    value={selectedTagFilter}
                    onChange={(e) => setSelectedTagFilter(e.target.value)}
                    style={{ marginLeft: 8, padding: '6px 10px', borderRadius: 8, border: '1px solid #cbd5e1', fontSize: 12, background: '#fff', color: '#334155' }}
                  >
                    <option value="">Todas as tags</option>
                    {availableTags.map((tag) => (
                      <option key={tag} value={tag}>{tag}</option>
                    ))}
                  </select>
                </div>
              </div>
            </div>

            <div className="stats-grid" style={{ marginBottom: 16 }}>
              <div className="stat-card stat-card--blue">
                <div className="stat-body">
                  <div className="stat-value">{filteredSummary.orders_count}</div>
                  <div className="stat-label">Pedidos</div>
                </div>
              </div>
              <div className="stat-card stat-card--green">
                <div className="stat-body">
                  <div className="stat-value">{filteredSummary.matched_items_count}</div>
                  <div className="stat-label">Itens Pedidos</div>
                </div>
              </div>
              <div className="stat-card stat-card--purple">
                <div className="stat-body">
                  <div className="stat-value">{productionProgressPct}%</div>
                  <div className="stat-label">Progresso de Produção (%)</div>
                </div>
              </div>
              <div className="stat-card stat-card--yellow">
                <div className="stat-body">
                  <div className="stat-value">{formatBRL(filteredSummary.total_matched)}</div>
                  <div className="stat-label">Total Faturado</div>
                </div>
              </div>
            </div>

            <div className="stats-grid" style={{ marginBottom: 16 }}>
              {itemFilterCards.map((card) => {
                const active = selectedItemStatusFilter === card.key;
                return (
                  <button
                    key={card.key}
                    type="button"
                    className="stat-card"
                    onClick={() => setSelectedItemStatusFilter((prev) => (prev === card.key ? null : card.key))}
                    style={{
                      cursor: 'pointer',
                      border: active ? '2px solid #2563eb' : '1px solid #e2e8f0',
                      background: active ? '#eff6ff' : '#fff',
                      textAlign: 'left',
                    }}
                  >
                    <div className="stat-body">
                      <div className="stat-value">{card.value}</div>
                      <div className="stat-label">{card.label}</div>
                    </div>
                  </button>
                );
              })}
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
                        const isExpanded = isExpandedMatch(expandedOrderId, gKey);
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
                                    <div style={{ fontSize: 12, color: '#64748b', marginBottom: 6 }}><strong>Email:</strong> {o.email || '—'}</div>
                                    <div style={{ fontSize: 12, color: '#64748b', marginBottom: 6 }}><strong>Nuvemshop:</strong> {o.numero_loja || '—'}</div>
                                    <div style={{ fontSize: 12, color: '#64748b', marginBottom: 8 }}><strong>Data:</strong> {formatDate(o.data)}</div>
                                    <div style={{ marginBottom: 8 }}><StatusBadge text={o.situacao} /></div>
                                    <div style={{ display: 'flex', justifyContent: 'space-between', gap: 8, fontSize: 12, color: '#64748b', marginBottom: 8 }}>
                                      <span><strong>Qtd:</strong> {o.quantity}</span>
                                    </div>
                                    <div style={{ marginBottom: 8 }}>
                                      <ProductionStatusBadge
                                        status={o.production_status}
                                        statusFeedback={statusFeedbackByItem[itemFeedbackKey(group.sku, o.order_id)] || 'idle'}
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
                          const isExpanded = isExpandedMatch(expandedOrderId, gKey);
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
                                            <td style={{ padding: '8px', color: '#334155' }}>
                                              <div style={{ fontWeight: 600 }}>{o.cliente || '—'}</div>
                                              <div style={{ fontSize: 12, color: '#64748b' }}>{o.email || '—'}</div>
                                            </td>
                                            <td style={{ padding: '8px' }}><StatusBadge text={o.situacao} /></td>
                                            <td style={{ padding: '8px' }}>
                                              <ProductionStatusBadge
                                                status={o.production_status}
                                                statusFeedback={statusFeedbackByItem[itemFeedbackKey(group.sku, o.order_id)] || 'idle'}
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
                ) : filteredOrdersByItemStatus.length === 0 ? (
                <div className="empty-state">
                  <span className="empty-state-icon">📭</span>
                  <p>Nenhuma venda encontrada para os produtos deste evento no período selecionado.</p>
                </div>
              ) : isMobile ? (
                <div style={{ display: 'grid', gap: 12, padding: 12 }}>
                  {filteredOrdersByItemStatus.map((order) => {
                    const orderKey = order.id || order.numero;
                    const isExpanded = isExpandedMatch(expandedOrderId, orderKey);
                    const matchedItems = Array.isArray(order.matched_items) ? order.matched_items : [];
                    const allEmbalado = matchedItems.length > 0 && matchedItems.every((i) => isFinalProductionStatus(i.production_status));

                    return (
                      <div key={orderKey} style={{ border: '1px solid #e2e8f0', borderRadius: 10, overflow: 'hidden', background: '#fff' }}>
                        <button
                          onClick={() => toggleOrder(orderKey)}
                          style={{ width: '100%', border: 'none', textAlign: 'left', background: isExpanded ? '#f0f9ff' : '#fff', padding: 14, cursor: 'pointer' }}
                        >
                          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: 8, marginBottom: 8 }}>
                            <div style={{ fontWeight: 700, color: '#1e293b' }}>Pedido {order.numero || order.id}</div>
                            <div style={{ fontWeight: 700, color: '#1e293b' }}>{formatBRL(order.total_matched)}</div>
                          </div>
                          <div style={{ fontSize: 13, color: '#334155', marginBottom: 2 }}>{order.cliente || '—'}</div>
                          <div style={{ fontSize: 12, color: '#64748b', marginBottom: 8 }}>{order.email || '—'}</div>
                          <div style={{ fontSize: 12, color: '#64748b', marginBottom: 6 }}><strong>Data:</strong> {formatDate(order.data)}</div>
                          <div style={{ fontSize: 12, color: '#475569', marginBottom: 8 }}><strong>Código:</strong> {order.numero_loja || '—'}</div>
                          <div style={{ fontSize: 12, color: '#475569', marginBottom: 8, display: 'grid', gap: 4 }}>
                            <div style={{ fontWeight: 700 }}>Tag:</div>
                            <EventOrderTagEditor
                              orderId={order.id}
                              currentTags={order.tags || (order.tag ? [order.tag] : [])}
                              availableTags={availableTags}
                              draftTagsByOrder={draftTagsByOrder}
                              setDraftTagsByOrder={setDraftTagsByOrder}
                              onAdd={handleOrderTagAdd}
                              onRemove={handleOrderTagRemove}
                              saving={!!tagSavingByOrder[String(order.id || '')]}
                              error={tagErrorByOrder[String(order.id || '')]}
                            />
                          </div>
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
                                      statusFeedback={statusFeedbackByItem[itemFeedbackKey(item.sku, order.id)] || 'idle'}
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
                      <th>Tag</th>
                      <th>Situação</th>
                      <th>Produção</th>
                      <th></th>
                      <th>Total Itens Evento</th>
                    </tr>
                  </thead>
                  <tbody>
                    {filteredOrdersByItemStatus.map((order) => {
                      const orderKey = order.id || order.numero;
                      const isExpanded = isExpandedMatch(expandedOrderId, orderKey);
                      const matchedItems = Array.isArray(order.matched_items) ? order.matched_items : [];
                      const allEmbalado = matchedItems.length > 0 && matchedItems.every((i) => isFinalProductionStatus(i.production_status));

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
                            <td>
                              <div style={{ fontWeight: 600 }}>{order.cliente || '—'}</div>
                              <div style={{ fontSize: 12, color: '#64748b' }}>{order.email || '—'}</div>
                            </td>
                            <td>
                              <EventOrderTagEditor
                                orderId={order.id}
                                currentTags={order.tags || (order.tag ? [order.tag] : [])}
                                availableTags={availableTags}
                                draftTagsByOrder={draftTagsByOrder}
                                setDraftTagsByOrder={setDraftTagsByOrder}
                                onAdd={handleOrderTagAdd}
                                onRemove={handleOrderTagRemove}
                                saving={!!tagSavingByOrder[String(order.id || '')]}
                                error={tagErrorByOrder[String(order.id || '')]}
                              />
                            </td>
                            <td><StatusBadge text={order.situacao} /></td>
                            <td style={{ fontSize: 12, color: '#64748b' }}>{order.production_summary || '—'}</td>
                            <td style={{ fontSize: 14 }} title={order.has_frete ? 'Envio' : 'Retirada'}>{order.has_frete ? '🚚' : '🏪'}</td>
                            <td style={{ fontWeight: 600 }}>{formatBRL(order.total_matched)}</td>
                          </tr>

                          {isExpanded && matchedItems.length > 0 && (
                            <tr style={{ background: '#f8fafc', borderTop: '2px solid #e2e8f0' }}>
                              <td colSpan="10" style={{ padding: '16px 20px' }}>
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
                                              statusFeedback={statusFeedbackByItem[itemFeedbackKey(item.sku, order.id)] || 'idle'}
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
