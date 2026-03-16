import React, { useState } from 'react';
import { DataTable, ConfirmDeleteModal, ErrorMessage } from './Modals';

/**
 * Componente de formulário de modelo
 */
export function ModelForm({ initialData, isEditing, onSubmit, onCancel }) {
  const [formData, setFormData] = useState(
    initialData || {
      code: '',
      name: '',
      allowed_sizes: [],
      size_order: [],
    }
  );
  const [sizeInput, setSizeInput] = useState('');
  const [dragIndex, setDragIndex] = useState(null);

  function handleAddSize() {
    if (sizeInput && !formData.allowed_sizes.includes(sizeInput)) {
      const newAllowed = [...formData.allowed_sizes, sizeInput];
      const newOrder = Array.isArray(formData.size_order) && formData.size_order.length > 0
        ? [...formData.size_order, sizeInput]
        : [...newAllowed];
      setFormData({
        ...formData,
        allowed_sizes: newAllowed,
        size_order: newOrder,
      });
      setSizeInput('');
    }
  }

  function handleRemoveSize(size) {
    const newAllowed = formData.allowed_sizes.filter(s => s !== size);
    const newOrder = (formData.size_order || []).filter(s => s !== size);
    setFormData({
      ...formData,
      allowed_sizes: newAllowed,
      size_order: newOrder,
    });
  }

  function handleDragReorder(dragIdx, dropIdx) {
    const newAllowed = [...formData.allowed_sizes];
    const [moved] = newAllowed.splice(dragIdx, 1);
    newAllowed.splice(dropIdx, 0, moved);
    setDragIndex(null);
    setFormData({
      ...formData,
      allowed_sizes: newAllowed,
      size_order: [...newAllowed],
    });
  }

  function handleSubmit(e) {
    e.preventDefault();
    onSubmit(formData);
  }

  return (
    <form onSubmit={handleSubmit} className="form">
      <input
        type="text"
        placeholder="Código (ex: CAM)"
        value={formData.code}
        onChange={(e) => setFormData({ ...formData, code: e.target.value })}
        disabled={isEditing}
        required
      />
      <input
        type="text"
        placeholder="Nome (ex: Camiseta)"
        value={formData.name}
        onChange={(e) => setFormData({ ...formData, name: e.target.value })}
        required
      />
      <div>
        <label>Tamanhos Permitidos:</label>
        <div className="size-input">
          <input
            type="text"
            placeholder="Adicionar tamanho"
            value={sizeInput}
            onChange={(e) => setSizeInput(e.target.value)}
            onKeyPress={(e) => e.key === 'Enter' && (e.preventDefault(), handleAddSize())}
          />
          <button type="button" onClick={handleAddSize}>
            +
          </button>
        </div>
        <div className="chips">
          {formData.allowed_sizes.map((size, idx) => (
            <span
              key={size}
              className={`chip draggable-chip ${dragIndex === idx ? 'dragging' : ''}`}
              draggable
              onDragStart={() => setDragIndex(idx)}
              onDragOver={(e) => e.preventDefault()}
              onDrop={() => handleDragReorder(dragIndex, idx)}
              onDragEnd={() => setDragIndex(null)}
            >
              {size}{' '}
              <button
                type="button"
                onClick={() => handleRemoveSize(size)}
              >
                ×
              </button>
            </span>
          ))}
        </div>
      </div>
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
 * Página de Modelos
 */
export function ModelsPage() {
  const [models, setModels] = React.useState([]);
  const [loading, setLoading] = React.useState(false);
  const [showForm, setShowForm] = React.useState(false);
  const [editingCode, setEditingCode] = React.useState(null);
  const [error, setError] = React.useState(null);
  const [confirmDelete, setConfirmDelete] = React.useState(null);

  const API_BASE = '/api';

  React.useEffect(() => {
    fetchModels();
  }, []);

  async function fetchModels() {
    try {
      setLoading(true);
      const resp = await fetch(`${API_BASE}/config/models`);
      if (!resp.ok) throw new Error('Failed to fetch models');
      const data = await resp.json();
      setModels(data);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }

  async function handleSaveModel(formData) {
    try {
      const url = editingCode
        ? `${API_BASE}/config/models/${editingCode}`
        : `${API_BASE}/config/models`;
      const method = editingCode ? 'PUT' : 'POST';

      const resp = await fetch(url, {
        method,
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(formData),
      });

      if (!resp.ok) {
        const err = await resp.json();
        throw new Error(err.detail?.message || 'Failed to save model');
      }

      setShowForm(false);
      setEditingCode(null);
      await fetchModels();
    } catch (err) {
      setError(err.message);
    }
  }

  async function handleDeleteModel(code) {
    try {
      const resp = await fetch(`${API_BASE}/config/models/${code}`, {
        method: 'DELETE',
      });
      if (!resp.ok) {
        const err = await resp.json().catch(() => ({}));
        throw new Error(err.detail?.message || 'Falha ao excluir o modelo');
      }
      setConfirmDelete(null);
      await fetchModels();
    } catch (err) {
      setError(err.message);
    }
  }

  return (
    <>
      <h2>Modelos</h2>
      <ErrorMessage error={error} onClose={() => setError(null)} />

      <button onClick={() => { setShowForm(!showForm); setEditingCode(null); }}>
        {showForm ? 'Cancelar' : '➕ Novo Modelo'}
      </button>

      {showForm && (
        <ModelForm
          initialData={
            editingCode
              ? models.find(m => m.code === editingCode)
              : undefined
          }
          isEditing={!!editingCode}
          onSubmit={handleSaveModel}
          onCancel={() => setShowForm(false)}
        />
      )}

      <DataTable
        columns={['Código', 'Nome', 'Tamanhos']}
        rows={models}
        renderCell={(row, col) => {
          if (col === 'Código') return row.code;
          if (col === 'Nome') return row.name;
          if (col === 'Tamanhos') return row.allowed_sizes.join(', ');
          return '';
        }}
        onEdit={(model) => {
          setEditingCode(model.code);
          setShowForm(true);
        }}
        onDelete={setConfirmDelete}
        loading={loading}
        emptyMessage="Nenhum modelo cadastrado."
      />

      {confirmDelete && (
        <ConfirmDeleteModal
          item={confirmDelete}
          resourceType="models"
          onConfirm={handleDeleteModel}
          onCancel={() => setConfirmDelete(null)}
        />
      )}
    </>
  );
}
