import { useState, useEffect } from 'react';

const API_BASE = 'http://localhost:8000';

/**
 * Hook para gerenciar estado da página Admin
 * Encapsula lógica comum de modelos, cores e templates
 */
export function useAdmin(resourceType) {
  const [items, setItems] = useState([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [showForm, setShowForm] = useState(false);
  const [editingCode, setEditingCode] = useState(null);

  // Endpoints
  const endpoints = {
    models: '/config/models',
    colors: '/config/colors',
    templates: '/config/templates',
  };

  const endpoint = endpoints[resourceType];

  /**
   * Busca items do backend
   */
  async function fetchItems() {
    try {
      setLoading(true);
      setError(null);
      const resp = await fetch(`${API_BASE}${endpoint}`);
      if (!resp.ok) throw new Error(`Failed to fetch ${resourceType}`);
      const data = await resp.json();
      setItems(data);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }

  /**
   * Cria ou atualiza um item
   */
  async function saveItem(itemData) {
    try {
      setError(null);
      const url = editingCode
        ? `${API_BASE}${endpoint}/${editingCode}`
        : `${API_BASE}${endpoint}`;
      const method = editingCode ? 'PUT' : 'POST';

      const resp = await fetch(url, {
        method,
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(itemData),
      });

      if (!resp.ok) {
        const err = await resp.json();
        throw new Error(err.detail?.message || `Failed to save ${resourceType}`);
      }

      setShowForm(false);
      setEditingCode(null);
      await fetchItems();
      return true;
    } catch (err) {
      setError(err.message);
      return false;
    }
  }

  /**
   * Deleta um item (soft delete)
   */
  async function deleteItem(code) {
    try {
      setError(null);
      const resp = await fetch(`${API_BASE}${endpoint}/${code}`, {
        method: 'DELETE',
      });

      if (!resp.ok) {
        const err = await resp.json().catch(() => ({}));
        throw new Error(err.detail?.message || `Failed to delete ${resourceType}`);
      }

      await fetchItems();
      return true;
    } catch (err) {
      setError(err.message);
      return false;
    }
  }

  /**
   * Abre formulário para editar item
   */
  function startEdit(item) {
    setEditingCode(item.code);
    setShowForm(true);
    return item;
  }

  /**
   * Abre formulário para novo item
   */
  function startNew() {
    setEditingCode(null);
    setShowForm(true);
  }

  /**
   * Fecha formulário
   */
  function closeForm() {
    setShowForm(false);
    setEditingCode(null);
  }

  useEffect(() => {
    fetchItems();
  }, [resourceType]);

  return {
    items,
    loading,
    error,
    showForm,
    editingCode,
    fetchItems,
    saveItem,
    deleteItem,
    startEdit,
    startNew,
    closeForm,
    setError,
  };
}
