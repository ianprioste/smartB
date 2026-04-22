export function normalizeSku(value) {
  return String(value || '').trim().toUpperCase();
}

function normalizeSkuList(values) {
  return Array.from(new Set(
    (Array.isArray(values) ? values : []).map((sku) => normalizeSku(sku)).filter(Boolean)
  ));
}

export function summarizePlannedDeletionRisk(plan) {
  const items = Array.isArray(plan?.items) ? plan.items : [];
  const sensitiveParents = items
    .filter((item) => Array.isArray(item?.planned_deletions) && item.planned_deletions.length > 0)
    .map((item) => {
      const uniquePlanned = normalizeSkuList(item.planned_deletions);
      return {
        sku: normalizeSku(item.sku),
        count: uniquePlanned.length,
        plannedDeletions: uniquePlanned,
      };
    });

  return {
    parentsWithPlannedDeletions: sensitiveParents.length,
    totalPlannedDeletionSkus: sensitiveParents.reduce((acc, item) => acc + item.count, 0),
    sensitiveParents,
  };
}

export function summarizeDeletionMismatch(item) {
  const planned = Array.isArray(item?.planned_deletions)
    ? item.planned_deletions.map((sku) => normalizeSku(sku)).filter(Boolean)
    : [];
  const unexpected = Array.isArray(item?.unexpected_removed_variations)
    ? item.unexpected_removed_variations.map((sku) => normalizeSku(sku)).filter(Boolean)
    : [];
  const missing = Array.isArray(item?.missing_planned_deletions)
    ? item.missing_planned_deletions.map((sku) => normalizeSku(sku)).filter(Boolean)
    : [];

  return {
    planned,
    unexpected,
    missing,
    hasMismatch: unexpected.length > 0 || missing.length > 0,
  };
}

export function summarizeOrphanCompositionDiagnostics(executionResult) {
  const summary = executionResult?.summary || {};
  const items = Array.isArray(executionResult?.results) ? executionResult.results : [];

  const rebuilt = normalizeSkuList([
    ...(summary.repaired_orphan_compositions || []),
    ...(summary.rebuilt_orphan_compositions || []),
    ...items.flatMap((item) => item?.repaired_orphan_compositions || []),
    ...items.filter((item) => item?.repair_action === 'orphan_composition_rebuilt').map((item) => item?.sku),
  ]);

  const dropped = normalizeSkuList([
    ...(summary.dropped_orphan_compositions || []),
    ...items.flatMap((item) => item?.dropped_orphan_compositions || []),
  ]);

  const retrySkipped = normalizeSkuList([
    ...(summary.retry_skipped_invalid_compositions || []),
    ...items.flatMap((item) => item?.retry_skipped_invalid_compositions || []),
  ]);

  const blocked = normalizeSkuList([
    ...(summary.blocked_orphan_compositions || []),
    ...items
      .filter((item) => item?.error_type === 'missing_parent_dependency'
        || item?.error_type === 'missing_base_dependency'
        || item?.error_type === 'missing_base_for_composition')
      .map((item) => item?.sku),
  ]);

  return {
    rebuilt,
    blocked,
    dropped,
    retrySkipped,
    hasDiagnostics: rebuilt.length > 0 || blocked.length > 0 || dropped.length > 0 || retrySkipped.length > 0,
  };
}
