import React, { useEffect, useRef, useState } from 'react';

const PRODUCTION_STATUSES = ['Pendente', 'Em produção', 'Produzido', 'Embalado'];

const PROD_COLORS = {
  Pendente: { bg: '#f1f5f9', color: '#475569', border: '#cbd5e1' },
  'Em produção': { bg: '#dbeafe', color: '#1e40af', border: '#93c5fd' },
  Produzido: { bg: '#dcfce7', color: '#166534', border: '#86efac' },
  Embalado: { bg: '#f3e8ff', color: '#6b21a8', border: '#c4b5fd' },
};

export function ProductionStatusBadge({ status, onChangeStatus }) {
  const [open, setOpen] = useState(false);
  const ref = useRef(null);
  const colors = PROD_COLORS[status] || PROD_COLORS.Pendente;

  useEffect(() => {
    if (!open) return;
    const handler = (e) => {
      if (ref.current && !ref.current.contains(e.target)) {
        setOpen(false);
      }
    };
    document.addEventListener('mousedown', handler);
    return () => document.removeEventListener('mousedown', handler);
  }, [open]);

  return (
    <span ref={ref} style={{ position: 'relative', display: 'inline-block' }}>
      <button
        onClick={(e) => {
          e.stopPropagation();
          setOpen((prev) => !prev);
        }}
        style={{
          cursor: 'pointer',
          border: `1.5px solid ${colors.border}`,
          padding: '3px 10px',
          borderRadius: 12,
          fontSize: 12,
          fontWeight: 600,
          background: colors.bg,
          color: colors.color,
          transition: 'all 0.15s ease',
          lineHeight: '18px',
        }}
      >
        {status || 'Pendente'}
      </button>

      {open && (
        <div
          style={{
            position: 'absolute',
            top: '100%',
            left: 0,
            marginTop: 4,
            background: '#fff',
            border: '1px solid #e2e8f0',
            borderRadius: 8,
            boxShadow: '0 4px 12px rgba(0,0,0,0.1)',
            zIndex: 50,
            minWidth: 140,
            overflow: 'hidden',
          }}
        >
          {PRODUCTION_STATUSES.map((nextStatus) => {
            const nextColors = PROD_COLORS[nextStatus];
            return (
              <div
                key={nextStatus}
                onClick={(e) => {
                  e.stopPropagation();
                  setOpen(false);
                  onChangeStatus?.(nextStatus);
                }}
                style={{
                  padding: '8px 14px',
                  cursor: 'pointer',
                  fontSize: 13,
                  background: nextStatus === status ? nextColors.bg : '#fff',
                  color: nextColors.color,
                  fontWeight: nextStatus === status ? 600 : 400,
                  borderLeft: `3px solid ${nextStatus === status ? nextColors.border : 'transparent'}`,
                  transition: 'background 0.1s',
                }}
                onMouseEnter={(e) => {
                  e.currentTarget.style.background = nextColors.bg;
                }}
                onMouseLeave={(e) => {
                  e.currentTarget.style.background = nextStatus === status ? nextColors.bg : '#fff';
                }}
              >
                {nextStatus}
              </div>
            );
          })}
        </div>
      )}
    </span>
  );
}

export function ProductionNotesInput({ initialValue, onChangeNotes, debounceMs = 800 }) {
  const [value, setValue] = useState(initialValue || '');
  const timerRef = useRef(null);

  useEffect(() => {
    setValue(initialValue || '');
  }, [initialValue]);

  useEffect(() => {
    return () => {
      if (timerRef.current) clearTimeout(timerRef.current);
    };
  }, []);

  return (
    <textarea
      value={value}
      onChange={(e) => {
        const text = e.target.value;
        setValue(text);
        if (timerRef.current) clearTimeout(timerRef.current);
        timerRef.current = setTimeout(() => {
          onChangeNotes?.(text);
        }, debounceMs);
      }}
      onClick={(e) => e.stopPropagation()}
      placeholder="Notas..."
      rows={1}
      style={{
        width: '100%',
        fontSize: 12,
        padding: '4px 8px',
        border: '1px solid #e2e8f0',
        borderRadius: 6,
        resize: 'vertical',
        fontFamily: 'inherit',
        color: '#334155',
        background: '#f8fafc',
        minHeight: 28,
        lineHeight: '18px',
      }}
    />
  );
}