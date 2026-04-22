/**
 * Shared order/item production status utilities used by both
 * OrdersPage and EventSalesPage.
 */

/**
 * Normalize a raw production_status string to a canonical key.
 * Keys: 'cancelado' | 'impedimento' | 'entregue' | 'embalado' | 'em_producao' | 'pendente'
 */
export function normalizeProductionStatus(value) {
  const status = (value || 'Pendente').toString().trim().toLowerCase();
  if (status.includes('cancel')) return 'cancelado';
  if (status.includes('imped')) return 'impedimento';
  if (status.includes('entreg')) return 'entregue';
  if (status.includes('embalad')) return 'embalado';
  if (status.includes('produ') || status.includes('andamento')) return 'em_producao';
  return 'pendente';
}

/**
 * Returns true when the item is considered "finalized"
 * (embalado or entregue).
 */
export function isFinalProductionStatus(value) {
  const key = normalizeProductionStatus(value);
  return key === 'embalado' || key === 'entregue';
}

/**
 * Count items whose production_status is finalized (embalado or entregue).
 */
export function countFinalizedItems(items) {
  return (Array.isArray(items) ? items : []).filter((item) =>
    isFinalProductionStatus(item?.production_status),
  ).length;
}

/**
 * Derive the order-level display status from its items' production statuses.
 * Follows the agreed precedence rules.
 *
 * @param {Array} items - items with a `production_status` field
 * @param {boolean} hasFrete - whether the order has shipping cost
 * @returns {string} display label
 */
export function deriveOrderStatusFromItems(items, hasFrete) {
  const statuses = (Array.isArray(items) ? items : []).map((item) =>
    normalizeProductionStatus(item?.production_status),
  );
  if (statuses.length === 0) return 'Em aberto';
  if (statuses.every((s) => s === 'cancelado')) return 'Cancelado';
  const nonCancelled = statuses.filter((s) => s !== 'cancelado');
  if (nonCancelled.length > 0) {
    if (nonCancelled.every((s) => s === 'entregue')) return 'Atendido';
    if (nonCancelled.every((s) => s === 'embalado')) {
      return hasFrete ? 'Pronto para envio' : 'Pronto para retirada';
    }
  }
  if (statuses.some((s) => s === 'impedimento')) return 'Impedido';
  if (statuses.every((s) => s === 'pendente')) return 'Em aberto';
  if (statuses.every((s) => s === 'embalado' || s === 'entregue')) {
    if (statuses.every((s) => s === 'entregue')) return 'Atendido';
    return hasFrete ? 'Pronto para envio' : 'Pronto para retirada';
  }
  if (statuses.every((s) => s === 'entregue')) return 'Atendido';
  if (statuses.some((s) => s === 'entregue')) return 'Parcialmente entregue';
  if (statuses.every((s) => s === 'embalado')) return hasFrete ? 'Pronto para envio' : 'Pronto para retirada';
  // Any item embalado or in production, but not all finalized → Em andamento
  if (statuses.some((s) => s === 'em_producao' || s === 'embalado')) return 'Em andamento';
  return 'Em aberto';
}
