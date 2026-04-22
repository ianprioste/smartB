import React from 'react';
import { ProductionStatusBadge, ProductionNotesInput } from './ProductionControls';
import { ParentChildStatusControl } from './ParentChildStatusControl';

function ChevronIcon({ isExpanded }) {
  return (
    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"
      style={{ transform: isExpanded ? 'rotate(90deg)' : 'rotate(0deg)', transition: 'transform 0.2s ease', display: 'block' }}>
      <polyline points="9 18 15 12 9 6" />
    </svg>
  );
}

export function ItemsFilterTab({
  groups,
  isMobile,
  expandedKey,
  onToggle,
  formatCurrency,
  renderStatus,
  onChangeStatus,
  onChangeNotes,
  getStatusFeedback,
}) {
  if (!groups || groups.length === 0) {
    return (
      <div style={{ padding: 48, textAlign: 'center' }}>
        <div style={{ fontSize: 36, marginBottom: 8 }}>📭</div>
        <p style={{ color: '#94a3b8', fontSize: 14, margin: 0 }}>Nenhum item encontrado.</p>
      </div>
    );
  }

  if (isMobile) {
    return (
      <div style={{ padding: 12, display: 'grid', gap: 12 }}>
        {groups.map((group) => {
          const key = group.sku || group.product_name;
          const expanded = expandedKey === key;
          return (
            <div key={key} style={{ border: '1px solid #e2e8f0', borderRadius: 10, overflow: 'hidden', background: '#fff' }}>
              <button
                onClick={() => onToggle(key)}
                style={{ width: '100%', textAlign: 'left', border: 'none', background: expanded ? '#f8fafc' : '#fff', padding: 14, cursor: 'pointer' }}
              >
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: 8, marginBottom: 8 }}>
                  <div style={{ fontWeight: 700, color: '#0f172a' }}>{group.sku || '—'}</div>
                  <div style={{ fontWeight: 700, color: '#0f172a' }}>{formatCurrency(group.total_paid)}</div>
                </div>
                <div style={{ fontSize: 13, color: '#334155', marginBottom: 6 }}>{group.product_name || '—'}</div>
                <div style={{ fontSize: 12, color: '#64748b' }}><strong>Qtd:</strong> {group.total_qty} • <strong>Pedidos:</strong> {group.orders.length}</div>
              </button>
              {expanded && (
                <div style={{ padding: 12, borderTop: '1px solid #e2e8f0', background: '#f8fafc', display: 'grid', gap: 10 }}>
                  <ParentChildStatusControl
                    childrenStatuses={group.orders.map((o) => o.production_status)}
                    onApplyStatus={async (nextStatus, opts) => {
                      if (!opts?.applyToChildren) return;
                      await Promise.all(group.orders.map((o) => onChangeStatus(group.sku, o, nextStatus)));
                    }}
                  />
                  {group.orders.map((o, idx) => (
                    <div key={`${key}-${o.order_id}-${idx}`} style={{ border: '1px solid #e2e8f0', borderRadius: 8, background: '#fff', padding: 10 }}>
                      <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 8 }}>
                        <div style={{ fontWeight: 700, color: '#1e293b' }}>Pedido {o.numero || o.order_id}</div>
                        <div style={{ fontWeight: 700, color: '#1e293b' }}>{formatCurrency(o.paid_total)}</div>
                      </div>
                      <div style={{ fontSize: 12, color: '#64748b', marginBottom: 8 }}>{o.cliente || '—'}</div>
                      <div style={{ marginBottom: 8 }}>
                        <ProductionStatusBadge
                          status={o.production_status}
                          statusFeedback={getStatusFeedback ? getStatusFeedback(group.sku, o) : 'idle'}
                          onChangeStatus={(nextStatus) => onChangeStatus(group.sku, o, nextStatus)}
                        />
                      </div>
                      <ProductionNotesInput
                        initialValue={o.notes}
                        status={o.production_status}
                        onChangeNotes={(notes) => onChangeNotes(group.sku, o, notes)}
                      />
                    </div>
                  ))}
                </div>
              )}
            </div>
          );
        })}
      </div>
    );
  }

  return (
    <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 14 }}>
      <thead>
        <tr style={{ borderBottom: '2px solid #f1f5f9' }}>
          <th style={{ width: 36, padding: '12px 8px' }}></th>
          <th style={{ textAlign: 'left', padding: '12px 12px', fontWeight: 700, color: '#64748b', fontSize: 12, textTransform: 'uppercase', letterSpacing: '.3px' }}>SKU</th>
          <th style={{ textAlign: 'left', padding: '12px 12px', fontWeight: 700, color: '#64748b', fontSize: 12, textTransform: 'uppercase', letterSpacing: '.3px' }}>Produto</th>
          <th style={{ textAlign: 'right', padding: '12px 12px', fontWeight: 700, color: '#64748b', fontSize: 12, textTransform: 'uppercase', letterSpacing: '.3px' }}>Qtd</th>
          <th style={{ textAlign: 'right', padding: '12px 12px', fontWeight: 700, color: '#64748b', fontSize: 12, textTransform: 'uppercase', letterSpacing: '.3px' }}>Pedidos</th>
          <th style={{ textAlign: 'right', padding: '12px 12px', fontWeight: 700, color: '#64748b', fontSize: 12, textTransform: 'uppercase', letterSpacing: '.3px' }}>Total</th>
        </tr>
      </thead>
      <tbody>
        {groups.map((group) => {
          const key = group.sku || group.product_name;
          const expanded = expandedKey === key;
          return (
            <React.Fragment key={key}>
              <tr onClick={() => onToggle(key)} style={{ cursor: 'pointer', borderBottom: '1px solid #f1f5f9', background: expanded ? '#f8fafc' : '#fff' }}>
                <td style={{ textAlign: 'center', padding: '10px 8px', color: '#cbd5e1' }}><ChevronIcon isExpanded={expanded} /></td>
                <td style={{ padding: '10px 12px', color: '#64748b', fontFamily: 'monospace' }}>{group.sku || '—'}</td>
                <td style={{ padding: '10px 12px', color: '#334155', fontWeight: 600 }}>{group.product_name || '—'}</td>
                <td style={{ padding: '10px 12px', textAlign: 'right', color: '#334155' }}>{group.total_qty}</td>
                <td style={{ padding: '10px 12px', textAlign: 'right', color: '#64748b' }}>{group.orders.length}</td>
                <td style={{ padding: '10px 12px', textAlign: 'right', fontWeight: 700, color: '#0f172a' }}>{formatCurrency(group.total_paid)}</td>
              </tr>
              {expanded && (
                <tr>
                  <td colSpan="6" style={{ padding: 0 }}>
                    <div style={{ margin: '0 16px 12px', padding: 16, background: '#f8fafc', borderRadius: 8, border: '1px solid #e2e8f0' }}>
                      <div style={{ marginBottom: 12 }}>
                        <ParentChildStatusControl
                          childrenStatuses={group.orders.map((o) => o.production_status)}
                          onApplyStatus={async (nextStatus, opts) => {
                            if (!opts?.applyToChildren) return;
                            await Promise.all(group.orders.map((o) => onChangeStatus(group.sku, o, nextStatus)));
                          }}
                        />
                      </div>
                      <table style={{ width: '100%', fontSize: 13, borderCollapse: 'collapse' }}>
                        <thead>
                          <tr style={{ borderBottom: '1px solid #e2e8f0' }}>
                            <th style={{ textAlign: 'left', padding: '6px 8px', fontWeight: 600, color: '#94a3b8', fontSize: 11, textTransform: 'uppercase' }}>Pedido</th>
                            <th style={{ textAlign: 'left', padding: '6px 8px', fontWeight: 600, color: '#94a3b8', fontSize: 11, textTransform: 'uppercase' }}>Cliente</th>
                            <th style={{ textAlign: 'left', padding: '6px 8px', fontWeight: 600, color: '#94a3b8', fontSize: 11, textTransform: 'uppercase' }}>Situação</th>
                            <th style={{ textAlign: 'left', padding: '6px 8px', fontWeight: 600, color: '#94a3b8', fontSize: 11, textTransform: 'uppercase' }}>Produção</th>
                            <th style={{ textAlign: 'right', padding: '6px 8px', fontWeight: 600, color: '#94a3b8', fontSize: 11, textTransform: 'uppercase' }}>Qtd</th>
                            <th style={{ textAlign: 'right', padding: '6px 8px', fontWeight: 600, color: '#94a3b8', fontSize: 11, textTransform: 'uppercase' }}>Total</th>
                            <th style={{ textAlign: 'left', padding: '6px 8px', fontWeight: 600, color: '#94a3b8', fontSize: 11, textTransform: 'uppercase' }}>Notas</th>
                          </tr>
                        </thead>
                        <tbody>
                          {group.orders.map((o, idx) => (
                            <tr key={`${key}-${o.order_id}-${idx}`} style={{ borderBottom: '1px solid #f1f5f9' }}>
                              <td style={{ padding: '7px 8px', fontWeight: 600 }}>{o.numero || o.order_id}</td>
                              <td style={{ padding: '7px 8px', color: '#334155' }}>{o.cliente || '—'}</td>
                              <td style={{ padding: '7px 8px' }}>{renderStatus ? renderStatus(o.situacao) : (o.situacao || '—')}</td>
                              <td style={{ padding: '7px 8px' }}>
                                <ProductionStatusBadge
                                  status={o.production_status}
                                  statusFeedback={getStatusFeedback ? getStatusFeedback(group.sku, o) : 'idle'}
                                  onChangeStatus={(nextStatus) => onChangeStatus(group.sku, o, nextStatus)}
                                />
                              </td>
                              <td style={{ textAlign: 'right', padding: '7px 8px', color: '#64748b' }}>{o.quantity}</td>
                              <td style={{ textAlign: 'right', padding: '7px 8px', fontWeight: 600, color: '#0f172a' }}>{formatCurrency(o.paid_total)}</td>
                              <td style={{ padding: '7px 8px', minWidth: 150 }}>
                                <ProductionNotesInput
                                  initialValue={o.notes}
                                  status={o.production_status}
                                  onChangeNotes={(notes) => onChangeNotes(group.sku, o, notes)}
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
  );
}
