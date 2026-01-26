import React from 'react';

/**
 * Modal de confirmação de exclusão
 * Usado por Models, Colors, etc.
 */
export function ConfirmDeleteModal({ item, resourceType, onConfirm, onCancel }) {
  if (!item) return null;

  const resourceLabel = {
    models: 'modelo',
    colors: 'cor',
    templates: 'template',
  }[resourceType] || 'item';

  return (
    <div className="modal-overlay" onClick={onCancel}>
      <div className="modal" onClick={(e) => e.stopPropagation()}>
        <h3>Confirmar exclusão</h3>
        <p>
          Tem certeza que deseja excluir o {resourceLabel}{' '}
          <strong>{item.name}</strong> ({item.code})?
        </p>
        <p className="helper-text">
          Esta ação desativa o {resourceLabel} e pode afetar configurações dependentes.
        </p>
        <div className="modal-actions">
          <button onClick={onCancel} style={{ background: '#64748b' }}>
            Cancelar
          </button>
          <button
            onClick={() => onConfirm(item.code)}
            style={{ background: '#dc2626' }}
          >
            Excluir
          </button>
        </div>
      </div>
    </div>
  );
}

/**
 * Modal de reauthenticação do Bling
 */
export function BlingReauthModal({ onClose, onRenew, pendingRetry }) {
  return (
    <div className="modal-overlay">
      <div className="modal">
        <h3>🔑 Token do Bling Expirado</h3>
        <p>O token de acesso ao Bling expirou e precisa ser renovado.</p>
        <p style={{ marginTop: '16px', fontSize: '0.95rem', color: '#666' }}>
          Ao clicar em "Renovar Token", você será redirecionado para o Bling para
          autorizar novamente. Após autorizar, você será redirecionado de volta.
        </p>
        <div className="modal-actions">
          <button onClick={onClose} style={{ background: '#64748b' }}>
            Cancelar
          </button>
          {!pendingRetry ? (
            <button onClick={onRenew} style={{ background: '#4CAF50' }}>
              🔄 Renovar Token Agora
            </button>
          ) : (
            <button onClick={onClose} style={{ background: '#3b82f6' }}>
              ✅ Tentar Novamente
            </button>
          )}
        </div>
      </div>
    </div>
  );
}

/**
 * Componente de erro
 */
export function ErrorMessage({ error, onClose }) {
  if (!error) return null;

  return (
    <div className="wizard-error">
      ⚠️ {error}
      {onClose && <button onClick={onClose}>×</button>}
    </div>
  );
}

/**
 * Tabela genérica
 */
export function DataTable({
  columns,
  rows,
  renderCell,
  onEdit,
  onDelete,
  loading,
  emptyMessage,
}) {
  if (loading) return <p>Carregando...</p>;
  if (rows.length === 0) return <p>{emptyMessage || 'Nenhum dado encontrado.'}</p>;

  return (
    <table className="table">
      <thead>
        <tr>
          {columns.map((col) => (
            <th key={col}>{col}</th>
          ))}
          {(onEdit || onDelete) && <th>Ações</th>}
        </tr>
      </thead>
      <tbody>
        {rows.map((row, idx) => (
          <tr key={row.id || idx}>
            {columns.map((col) => (
              <td key={col}>{renderCell ? renderCell(row, col) : row[col]}</td>
            ))}
            {(onEdit || onDelete) && (
              <td>
                <div style={{ display: 'flex', gap: '8px' }}>
                  {onEdit && (
                    <button onClick={() => onEdit(row)}>Editar</button>
                  )}
                  {onDelete && (
                    <button
                      style={{ background: '#dc2626' }}
                      onClick={() => onDelete(row)}
                    >
                      Excluir
                    </button>
                  )}
                </div>
              </td>
            )}
          </tr>
        ))}
      </tbody>
    </table>
  );
}
