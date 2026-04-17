import React, { useMemo, useState } from 'react';
import { ProductionStatusBadge } from './ProductionControls';

export function ParentChildStatusControl({
  childrenStatuses = [],
  onApplyStatus,
  label = 'Aplicar status no item pai e filhos',
}) {
  const [applyToChildren, setApplyToChildren] = useState(true);

  const parentStatus = useMemo(() => {
    const values = (childrenStatuses || []).filter(Boolean);
    if (values.length === 0) return 'Pendente';
    const unique = new Set(values);
    if (unique.size === 1) return values[0];
    return values[0];
  }, [childrenStatuses]);

  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: 10, flexWrap: 'wrap' }}>
      <ProductionStatusBadge
        status={parentStatus}
        onChangeStatus={(nextStatus) => onApplyStatus?.(nextStatus, { applyToChildren })}
      />
      <label style={{ display: 'inline-flex', alignItems: 'center', gap: 6, fontSize: 12, color: '#64748b' }}>
        <input
          type="checkbox"
          checked={applyToChildren}
          onChange={(e) => setApplyToChildren(Boolean(e.target.checked))}
        />
        {label}
      </label>
    </div>
  );
}
