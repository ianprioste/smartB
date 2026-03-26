import React, { useEffect, useMemo, useState } from 'react';
import { Layout } from '../../components/Layout';

const API_BASE = '/api';

export function AccessControlPage() {
  const [profiles, setProfiles] = useState([]);
  const [users, setUsers] = useState([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  const [newProfileName, setNewProfileName] = useState('');
  const [newProfileDesc, setNewProfileDesc] = useState('');

  const [newUserEmail, setNewUserEmail] = useState('');
  const [newUserProfileId, setNewUserProfileId] = useState('');
  const [newUserPassword, setNewUserPassword] = useState('');

  const profileOptions = useMemo(() => profiles.filter((p) => p.is_active), [profiles]);

  async function loadAll() {
    setLoading(true);
    setError('');
    try {
      const [pResp, uResp] = await Promise.all([
        fetch(`${API_BASE}/auth/access/profiles`, { credentials: 'include' }),
        fetch(`${API_BASE}/auth/access/users`, { credentials: 'include' }),
      ]);
      const pData = await pResp.json();
      const uData = await uResp.json();

      if (!pResp.ok) throw new Error(pData.detail || 'Falha ao carregar perfis');
      if (!uResp.ok) throw new Error(uData.detail || 'Falha ao carregar usuários');

      setProfiles(Array.isArray(pData.data) ? pData.data : []);
      setUsers(Array.isArray(uData.data) ? uData.data : []);
      if (!newUserProfileId && Array.isArray(pData.data) && pData.data.length > 0) {
        setNewUserProfileId(pData.data[0].id);
      }
    } catch (err) {
      setError(err.message || 'Erro ao carregar gestão de acesso');
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    loadAll();
  }, []);

  async function createProfile(e) {
    e.preventDefault();
    if (!newProfileName.trim()) return;
    setError('');

    const resp = await fetch(`${API_BASE}/auth/access/profiles`, {
      method: 'POST',
      credentials: 'include',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ name: newProfileName.trim(), description: newProfileDesc.trim() || null }),
    });
    const data = await resp.json().catch(() => ({}));
    if (!resp.ok) {
      setError(data.detail || 'Falha ao criar perfil');
      return;
    }

    setNewProfileName('');
    setNewProfileDesc('');
    await loadAll();
  }

  async function createUser(e) {
    e.preventDefault();
    if (!newUserEmail.trim() || !newUserProfileId) return;
    setError('');

    const resp = await fetch(`${API_BASE}/auth/access/users`, {
      method: 'POST',
      credentials: 'include',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ email: newUserEmail.trim(), profile_id: newUserProfileId, password: newUserPassword }),
    });
    const data = await resp.json().catch(() => ({}));
    if (!resp.ok) {
      setError(data.detail || 'Falha ao cadastrar e-mail');
      return;
    }

    setNewUserEmail('');
    setNewUserPassword('');
    await loadAll();
  }

  async function toggleUserStatus(user) {
    setError('');
    const resp = await fetch(`${API_BASE}/auth/access/users/${user.id}`, {
      method: 'PATCH',
      credentials: 'include',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ is_active: !user.is_active }),
    });
    const data = await resp.json().catch(() => ({}));
    if (!resp.ok) {
      setError(data.detail || 'Falha ao atualizar usuário');
      return;
    }
    await loadAll();
  }

  async function changeUserPassword(user) {
    setError('');
    const newPassword = window.prompt(`Nova senha para ${user.email}:`);
    if (newPassword === null) return;

    const password = newPassword.trim();
    if (password.length < 6) {
      setError('A senha deve ter pelo menos 6 caracteres');
      return;
    }

    const resp = await fetch(`${API_BASE}/auth/access/users/${user.id}`, {
      method: 'PATCH',
      credentials: 'include',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ password }),
    });
    const data = await resp.json().catch(() => ({}));
    if (!resp.ok) {
      setError(data.detail || 'Falha ao alterar senha');
      return;
    }
    await loadAll();
  }

  async function removeUser(userId) {
    setError('');
    const resp = await fetch(`${API_BASE}/auth/access/users/${userId}`, {
      method: 'DELETE',
      credentials: 'include',
    });
    const data = await resp.json().catch(() => ({}));
    if (!resp.ok) {
      setError(data.detail || 'Falha ao remover usuário');
      return;
    }
    await loadAll();
  }

  return (
    <Layout>
      <div className="page-inner">
        <div className="page-header">
          <div>
            <h2>Gestão de Acesso</h2>
            <p className="page-subtitle">Somente e-mails cadastrados podem acessar o aplicativo</p>
          </div>
          <button className="btn-secondary" onClick={loadAll} disabled={loading}>
            {loading ? 'Atualizando...' : 'Atualizar'}
          </button>
        </div>

        {error && <div className="error">{error}</div>}

        <div className="stats-grid" style={{ marginBottom: 16 }}>
          <div className="stat-card stat-card--blue">
            <div className="stat-body">
              <div className="stat-value">{profiles.length}</div>
              <div className="stat-label">Perfis de Acesso</div>
            </div>
          </div>
          <div className="stat-card stat-card--green">
            <div className="stat-body">
              <div className="stat-value">{users.length}</div>
              <div className="stat-label">E-mails Cadastrados</div>
            </div>
          </div>
          <div className="stat-card stat-card--yellow">
            <div className="stat-body">
              <div className="stat-value">{users.filter((u) => u.is_active).length}</div>
              <div className="stat-label">E-mails Ativos</div>
            </div>
          </div>
        </div>

        <div className="card" style={{ marginBottom: 16 }}>
          <div className="card-header">
            <h3>🧩 Perfis de Acesso</h3>
          </div>
          <div style={{ padding: 20 }}>
            <form onSubmit={createProfile} style={{ display: 'grid', gridTemplateColumns: '2fr 3fr auto', gap: 12, marginBottom: 16 }}>
              <input
                type="text"
                placeholder="Nome do perfil"
                value={newProfileName}
                onChange={(e) => setNewProfileName(e.target.value)}
              />
              <input
                type="text"
                placeholder="Descrição (opcional)"
                value={newProfileDesc}
                onChange={(e) => setNewProfileDesc(e.target.value)}
              />
              <button className="btn-primary" type="submit">Adicionar Perfil</button>
            </form>

            <table className="table">
              <thead>
                <tr>
                  <th>Perfil</th>
                  <th>Descrição</th>
                  <th>Status</th>
                </tr>
              </thead>
              <tbody>
                {profiles.map((p) => (
                  <tr key={p.id}>
                    <td style={{ fontWeight: 600 }}>{p.name}</td>
                    <td>{p.description || '—'}</td>
                    <td>{p.is_active ? 'Ativo' : 'Inativo'}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>

        <div className="card">
          <div className="card-header">
            <h3>📧 E-mails Autorizados</h3>
          </div>
          <div style={{ padding: 20 }}>
            <form onSubmit={createUser} style={{ display: 'grid', gridTemplateColumns: '3fr 2fr 2fr auto', gap: 12, marginBottom: 16 }}>
              <input
                type="email"
                placeholder="email@empresa.com"
                value={newUserEmail}
                onChange={(e) => setNewUserEmail(e.target.value)}
              />
              <input
                type="password"
                placeholder="Senha inicial"
                required
                value={newUserPassword}
                onChange={(e) => setNewUserPassword(e.target.value)}
              />
              <select value={newUserProfileId} onChange={(e) => setNewUserProfileId(e.target.value)}>
                {profileOptions.map((p) => (
                  <option value={p.id} key={p.id}>{p.name}</option>
                ))}
              </select>
              <button className="btn-primary" type="submit">Adicionar</button>
            </form>

            <table className="table">
              <thead>
                <tr>
                  <th>E-mail</th>
                  <th>Perfil</th>
                  <th>Status</th>
                  <th>Ações</th>
                </tr>
              </thead>
              <tbody>
                {users.map((u) => (
                  <tr key={u.id}>
                    <td>{u.email}</td>
                    <td>{u.profile?.name || '—'}</td>
                    <td>{u.is_active ? 'Ativo' : 'Inativo'}</td>
                    <td style={{ display: 'flex', gap: 8 }}>
                      <button className="btn-secondary" onClick={() => toggleUserStatus(u)}>
                        {u.is_active ? 'Desativar' : 'Ativar'}
                      </button>
                      <button className="btn-secondary" onClick={() => changeUserPassword(u)}>
                        Alterar senha
                      </button>
                      <button className="btn-secondary" onClick={() => removeUser(u.id)}>Remover</button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      </div>
    </Layout>
  );
}
