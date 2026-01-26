import React, { useState } from 'react';
import { DataTable, ConfirmDeleteModal, ErrorMessage } from './Modals';

/**
 * Componente de formulário de cor
 */
export function ColorForm({ initialData, isEditing, onSubmit, onCancel }) {
  const [formData, setFormData] = useState(
    initialData || {
      code: '',
      name: '',
    }
  );

  function handleSubmit(e) {
    e.preventDefault();
    onSubmit(formData);
  }

  return (
    <form onSubmit={handleSubmit} className="form">
      <input
        type="text"
        placeholder="Código (ex: BR)"
        value={formData.code}
        onChange={(e) => setFormData({ ...formData, code: e.target.value })}
        disabled={isEditing}
        required
      />
      <input
        type="text"
        placeholder="Nome (ex: Branca)"
        value={formData.name}
        onChange={(e) => setFormData({ ...formData, name: e.target.value })}
        required
      />
      <div style={{ display: 'flex', gap: '8px' }}>
        <button type="submit">Salvar</button>
        <button type="button" onClick={onCancel} className="btn-secondary">
          Cancelar
        </button>
      </div>
    </form>
  );
}

/**
 * Página de Cores
 */
export function ColorsPage() {
  const [colors, setColors] = React.useState([]);
  const [loading, setLoading] = React.useState(false);
  const [showForm, setShowForm] = React.useState(false);
  const [editingCode, setEditingCode] = React.useState(null);
  const [error, setError] = React.useState(null);
  const [confirmDelete, setConfirmDelete] = React.useState(null);

  const API_BASE = 'http://localhost:8000';

  React.useEffect(() => {
    fetchColors();
  }, []);

  async function fetchColors() {
    try {
      setLoading(true);
      const resp = await fetch(`${API_BASE}/config/colors`);
      if (!resp.ok) throw new Error('Failed to fetch colors');
      const data = await resp.json();
      setColors(data);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }

  async function handleSaveColor(formData) {
    try {
      const url = editingCode
        ? `${API_BASE}/config/colors/${editingCode}`
        : `${API_BASE}/config/colors`;
      const method = editingCode ? 'PUT' : 'POST';

      const resp = await fetch(url, {
        method,
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(formData),
      });

      if (!resp.ok) {
        const err = await resp.json();
        throw new Error(err.detail?.message || 'Failed to save color');
      }

      setShowForm(false);
      setEditingCode(null);
      await fetchColors();
    } catch (err) {
      setError(err.message);
    }
  }

  async function handleDeleteColor(code) {
    try {
      const resp = await fetch(`${API_BASE}/config/colors/${code}`, {
        method: 'DELETE',
      });
      if (!resp.ok) {
        const err = await resp.json().catch(() => ({}));
        throw new Error(err.detail?.message || 'Falha ao excluir a cor');
      }
      setConfirmDelete(null);
      await fetchColors();
    } catch (err) {
      setError(err.message);
    }
  }

  return (
    <>
      <h2>Cores</h2>
      <ErrorMessage error={error} onClose={() => setError(null)} />

      <button onClick={() => { setShowForm(!showForm); setEditingCode(null); }}>
        {showForm ? 'Cancelar' : '➕ Nova Cor'}
      </button>

      {showForm && (
        <ColorForm
          initialData={
            editingCode
              ? colors.find(c => c.code === editingCode)
              : undefined
          }
          isEditing={!!editingCode}
          onSubmit={handleSaveColor}
          onCancel={() => setShowForm(false)}
        />
      )}

      <DataTable
        columns={['Código', 'Nome']}
        rows={colors}
        renderCell={(row, col) => {
          if (col === 'Código') return row.code;
          if (col === 'Nome') return row.name;
          return '';
        }}
        onEdit={(color) => {
          setEditingCode(color.code);
          setShowForm(true);
        }}
        onDelete={setConfirmDelete}
        loading={loading}
        emptyMessage="Nenhuma cor cadastrada."
      />

      {confirmDelete && (
        <ConfirmDeleteModal
          item={confirmDelete}
          resourceType="colors"
          onConfirm={handleDeleteColor}
          onCancel={() => setConfirmDelete(null)}
        />
      )}
    </>
  );
}
