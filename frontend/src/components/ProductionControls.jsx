import React, { useEffect, useRef, useState } from 'react';

const PRODUCTION_STATUSES = ['Pendente', 'Em produção', 'Produzido', 'Embalado', 'Impedimento'];
const IMPEDIMENT_LABEL = 'Motivo do Impedimento:';

const PROD_COLORS = {
  Pendente: { bg: '#f1f5f9', color: '#475569', border: '#cbd5e1' },
  'Em produção': { bg: '#dbeafe', color: '#1e40af', border: '#93c5fd' },
  Produzido: { bg: '#dcfce7', color: '#166534', border: '#86efac' },
  Embalado: { bg: '#f3e8ff', color: '#6b21a8', border: '#c4b5fd' },
  Impedimento: { bg: '#fee2e2', color: '#991b1b', border: '#fca5a5' },
};

export function ProductionStatusBadge({ status, onChangeStatus }) {
  const [open, setOpen] = useState(false);
  const [openUpward, setOpenUpward] = useState(false);
  const ref = useRef(null);
  const menuRef = useRef(null);
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

  useEffect(() => {
    if (!open) return;

    const updatePlacement = () => {
      const rootRect = ref.current?.getBoundingClientRect();
      if (!rootRect) return;

      const menuHeight = menuRef.current?.offsetHeight || 220;
      const viewportHeight = window.innerHeight || document.documentElement.clientHeight;
      const spaceBelow = viewportHeight - rootRect.bottom;
      const spaceAbove = rootRect.top;
      const shouldOpenUpward = spaceBelow < menuHeight + 8 && spaceAbove > spaceBelow;
      setOpenUpward(shouldOpenUpward);
    };

    updatePlacement();
    window.addEventListener('resize', updatePlacement);
    window.addEventListener('scroll', updatePlacement, true);

    return () => {
      window.removeEventListener('resize', updatePlacement);
      window.removeEventListener('scroll', updatePlacement, true);
    };
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
          ref={menuRef}
          style={{
            position: 'absolute',
            top: openUpward ? 'auto' : '100%',
            bottom: openUpward ? '100%' : 'auto',
            left: 0,
            marginTop: openUpward ? 0 : 4,
            marginBottom: openUpward ? 4 : 0,
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

function splitStoredNotes(rawValue) {
  const text = rawValue || '';
  const index = text.indexOf(IMPEDIMENT_LABEL);
  if (index === -1) {
    return { notes: text, impedimentReason: '' };
  }

  const notes = text.slice(0, index).replace(/\s+$/, '');
  const reason = text.slice(index + IMPEDIMENT_LABEL.length).trim();
  return { notes, impedimentReason: reason };
}

function composeStoredNotes(notes, impedimentReason, status) {
  const base = (notes || '').trim();
  const reason = (impedimentReason || '').trim();

  if (status === 'Impedimento' && reason) {
    return base ? `${base}\n\n${IMPEDIMENT_LABEL} ${reason}` : `${IMPEDIMENT_LABEL} ${reason}`;
  }

  return base;
}

export function ProductionNotesInput({ initialValue, status, onChangeNotes, debounceMs = 800 }) {
  const parsed = splitStoredNotes(initialValue || '');
  const [value, setValue] = useState(parsed.notes);
  const [impedimentReason, setImpedimentReason] = useState(parsed.impedimentReason);
  const timerRef = useRef(null);
  const valueRef = useRef(parsed.notes);
  const impedimentReasonRef = useRef(parsed.impedimentReason);
  const lastSavedRef = useRef(composeStoredNotes(parsed.notes, parsed.impedimentReason, status));

  useEffect(() => {
    const nextParsed = splitStoredNotes(initialValue || '');
    setValue(nextParsed.notes);
    setImpedimentReason(nextParsed.impedimentReason);
    valueRef.current = nextParsed.notes;
    impedimentReasonRef.current = nextParsed.impedimentReason;
    lastSavedRef.current = composeStoredNotes(nextParsed.notes, nextParsed.impedimentReason, status);
  }, [initialValue]);

  useEffect(() => {
    return () => {
      if (timerRef.current) {
        clearTimeout(timerRef.current);
        timerRef.current = null;
        const nextPayload = composeStoredNotes(valueRef.current, impedimentReasonRef.current, status);
        if (nextPayload !== lastSavedRef.current) {
          onChangeNotes?.(nextPayload);
          lastSavedRef.current = nextPayload;
        }
      }
    };
  }, [onChangeNotes, status]);

  const commitNow = (nextValue, nextReason) => {
    if (timerRef.current) {
      clearTimeout(timerRef.current);
      timerRef.current = null;
    }
    const nextPayload = composeStoredNotes(nextValue, nextReason, status);
    if (nextPayload !== lastSavedRef.current) {
      onChangeNotes?.(nextPayload);
      lastSavedRef.current = nextPayload;
    }
  };

  const scheduleSave = (nextValue, nextReason) => {
    valueRef.current = nextValue;
    impedimentReasonRef.current = nextReason;
    if (timerRef.current) clearTimeout(timerRef.current);
    timerRef.current = setTimeout(() => {
      commitNow(nextValue, nextReason);
    }, debounceMs);
  };

  const isImpedimento = status === 'Impedimento';

  return (
    <div style={{ display: 'grid', gap: 8 }}>
      <textarea
        value={value}
        onChange={(e) => {
          const text = e.target.value;
          setValue(text);
          scheduleSave(text, impedimentReason);
        }}
        onBlur={() => commitNow(valueRef.current, impedimentReasonRef.current)}
        onClick={(e) => e.stopPropagation()}
        placeholder="Notas..."
        rows={1}
        style={{
          width: '100%',
          fontSize: 12,
          padding: '4px 8px',
          border: `1px solid ${isImpedimento ? '#fecaca' : '#e2e8f0'}`,
          borderRadius: 6,
          resize: 'vertical',
          fontFamily: 'inherit',
          color: '#334155',
          background: isImpedimento ? '#fff1f2' : '#f8fafc',
          minHeight: 28,
          lineHeight: '18px',
          transition: 'border-color 0.2s, background-color 0.2s',
        }}
      />

      {isImpedimento && (
        <div 
          onClick={(e) => e.stopPropagation()}
          style={{
            padding: 10,
            background: '#fee2e2',
            border: '2px solid #fca5a5',
            borderRadius: 6,
            display: 'grid',
            gap: 8,
          }}
        >
          <label style={{ display: 'block', fontSize: 12, fontWeight: 700, color: '#991b1b', margin: 0 }}>
            🚫 {IMPEDIMENT_LABEL}
          </label>
          <textarea
            value={impedimentReason}
            onChange={(e) => {
              const text = e.target.value;
              setImpedimentReason(text);
              scheduleSave(value, text);
            }}
            onBlur={() => commitNow(valueRef.current, impedimentReasonRef.current)}
            placeholder="Descreva o motivo do impedimento..."
            rows={3}
            style={{
              width: '100%',
              fontSize: 12,
              padding: '8px 10px',
              border: '1px solid #fca5a5',
              borderRadius: 4,
              resize: 'vertical',
              fontFamily: 'inherit',
              color: '#7f1d1d',
              background: '#fef2f2',
              minHeight: 60,
              lineHeight: '18px',
              boxSizing: 'border-box',
            }}
          />
        </div>
      )}
    </div>
  );
}