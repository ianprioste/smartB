import { useState, useEffect } from 'react';

const API_BASE = '/api';

/**
 * Hook para chamadas comuns à API
 * Encapsula fetch logic e tratamento de erros
 */
export function useApi() {
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  /**
   * Faz GET request
   */
  async function get(endpoint) {
    try {
      setLoading(true);
      setError(null);
      const resp = await fetch(`${API_BASE}${endpoint}`);
      if (!resp.ok) {
        const err = await resp.json().catch(() => ({}));
        throw new Error(err.detail?.message || 'Request failed');
      }
      return await resp.json();
    } catch (err) {
      setError(err.message);
      throw err;
    } finally {
      setLoading(false);
    }
  }

  /**
   * Faz POST request
   */
  async function post(endpoint, data) {
    try {
      setLoading(true);
      setError(null);
      const resp = await fetch(`${API_BASE}${endpoint}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(data),
      });
      if (!resp.ok) {
        const err = await resp.json().catch(() => ({}));
        throw new Error(err.detail?.message || 'Request failed');
      }
      return await resp.json();
    } catch (err) {
      setError(err.message);
      throw err;
    } finally {
      setLoading(false);
    }
  }

  /**
   * Faz PUT request
   */
  async function put(endpoint, data) {
    try {
      setLoading(true);
      setError(null);
      const resp = await fetch(`${API_BASE}${endpoint}`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(data),
      });
      if (!resp.ok) {
        const err = await resp.json().catch(() => ({}));
        throw new Error(err.detail?.message || 'Request failed');
      }
      return await resp.json();
    } catch (err) {
      setError(err.message);
      throw err;
    } finally {
      setLoading(false);
    }
  }

  /**
   * Faz DELETE request
   */
  async function del(endpoint) {
    try {
      setLoading(true);
      setError(null);
      const resp = await fetch(`${API_BASE}${endpoint}`, {
        method: 'DELETE',
      });
      if (!resp.ok) {
        const err = await resp.json().catch(() => ({}));
        throw new Error(err.detail?.message || 'Request failed');
      }
      return await resp.json();
    } catch (err) {
      setError(err.message);
      throw err;
    } finally {
      setLoading(false);
    }
  }

  return {
    loading,
    error,
    get,
    post,
    put,
    del,
    setError,
  };
}
