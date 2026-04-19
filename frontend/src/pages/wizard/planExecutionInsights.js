export function normalizeSku(value) {
  return String(value || '').trim().toUpperCase();
}

export function summarizePlannedDeletionRisk(plan) {
  const items = Array.isArray(plan?.items) ? plan.items : [];
  const sensitiveParents = items
    .filter((item) => Array.isArray(item?.planned_deletions) && item.planned_deletions.length > 0)
    .map((item) => {
      const uniquePlanned = Array.from(
        new Set(item.planned_deletions.map((sku) => normalizeSku(sku)).filter(Boolean))
      );
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