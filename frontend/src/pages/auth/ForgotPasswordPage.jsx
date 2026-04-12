import React, { useMemo, useState } from 'react';
import { useLocation, useNavigate } from 'react-router-dom';

const API_BASE = '/api';

const cardStyle = {
  width: '100%',
  maxWidth: 460,
  background: '#ffffff',
  borderRadius: 16,
  boxShadow: '0 20px 50px rgba(15, 23, 42, 0.08)',
  border: '1px solid #e2e8f0',
};

function StepIndicator({ currentStep }) {
  const steps = [
    { id: 1, label: 'E-mail' },
    { id: 2, label: 'Código' },
    { id: 3, label: 'Nova senha' },
  ];

  return (
    <div style={{ display: 'flex', gap: 8, marginBottom: 18, flexWrap: 'wrap' }}>
      {steps.map((step) => {
        const active = currentStep === step.id;
        const done = currentStep > step.id;
        return (
          <div
            key={step.id}
            style={{
              padding: '6px 12px',
              borderRadius: 999,
              fontSize: 12,
              fontWeight: 700,
              background: active ? '#dbeafe' : done ? '#dcfce7' : '#f1f5f9',
              color: active ? '#1d4ed8' : done ? '#166534' : '#64748b',
            }}
          >
            {step.id}. {step.label}
          </div>
        );
      })}
    </div>
  );
}

export function ForgotPasswordPage() {
  const navigate = useNavigate();
  const location = useLocation();
  const initialEmail = useMemo(() => (location.state?.email || '').trim().toLowerCase(), [location.state]);

  const [step, setStep] = useState(1);
  const [email, setEmail] = useState(initialEmail);
  const [code, setCode] = useState('');
  const [newPassword, setNewPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [loading, setLoading] = useState(false);
  const [message, setMessage] = useState('');
  const [error, setError] = useState('');

  async function handleRequestCode(e) {
    e.preventDefault();
    setLoading(true);
    setError('');
    setMessage('');

    try {
      const resp = await fetch(`${API_BASE}/auth/access/forgot-password/request`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ email }),
      });
      const data = await resp.json().catch(() => ({}));
      if (!resp.ok) {
        throw new Error(data.detail || 'Falha ao enviar código');
      }
      setMessage(data.message || 'Código enviado para o e-mail informado');
      setStep(2);
    } catch (err) {
      setError(err.message || 'Falha ao enviar código');
    } finally {
      setLoading(false);
    }
  }

  async function handleVerifyCode(e) {
    e.preventDefault();
    setLoading(true);
    setError('');
    setMessage('');

    try {
      const resp = await fetch(`${API_BASE}/auth/access/forgot-password/verify`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ email, code }),
      });
      const data = await resp.json().catch(() => ({}));
      if (!resp.ok) {
        throw new Error(data.detail || 'Código inválido ou expirado');
      }
      setMessage(data.message || 'Código validado com sucesso');
      setStep(3);
    } catch (err) {
      setError(err.message || 'Código inválido ou expirado');
    } finally {
      setLoading(false);
    }
  }

  async function handleResetPassword(e) {
    e.preventDefault();
    setLoading(true);
    setError('');
    setMessage('');

    try {
      if (newPassword !== confirmPassword) {
        throw new Error('As senhas não coincidem');
      }

      const resp = await fetch(`${API_BASE}/auth/access/forgot-password/reset`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ email, code, new_password: newPassword }),
      });
      const data = await resp.json().catch(() => ({}));
      if (!resp.ok) {
        throw new Error(data.detail || 'Falha ao redefinir senha');
      }

      navigate('/login', {
        replace: true,
        state: {
          email,
          resetSuccess: data.message || 'Senha alterada com sucesso. Faça login novamente.',
        },
      });
    } catch (err) {
      setError(err.message || 'Falha ao redefinir senha');
    } finally {
      setLoading(false);
    }
  }

  return (
    <div style={{ minHeight: '100vh', display: 'grid', placeItems: 'center', background: 'linear-gradient(135deg, #f8fafc 0%, #e2e8f0 100%)', padding: 16 }}>
      <div style={cardStyle}>
        <div style={{ padding: 24, borderBottom: '1px solid #e2e8f0' }}>
          <h2 style={{ margin: 0, color: '#0f172a' }}>Recuperar Senha</h2>
          <p style={{ margin: '6px 0 0', color: '#64748b', fontSize: 14 }}>
            Receba um código por e-mail, valide e defina sua nova senha.
          </p>
        </div>

        <div style={{ padding: 24 }}>
          <StepIndicator currentStep={step} />

          {message && <div className="info-box" style={{ marginBottom: 12 }}><p>{message}</p></div>}
          {error && <div className="error" style={{ marginBottom: 12 }}>{error}</div>}

          {step === 1 && (
            <form onSubmit={handleRequestCode}>
              <div className="form-group" style={{ marginBottom: 16 }}>
                <label htmlFor="recovery-email">E-mail</label>
                <input
                  id="recovery-email"
                  type="email"
                  required
                  value={email}
                  placeholder="nome@empresa.com"
                  onChange={(e) => setEmail(e.target.value)}
                />
              </div>
              <button type="submit" className="btn-primary" disabled={loading} style={{ width: '100%' }}>
                {loading ? 'Enviando código...' : 'Enviar código'}
              </button>
            </form>
          )}

          {step === 2 && (
            <form onSubmit={handleVerifyCode}>
              <div className="form-group" style={{ marginBottom: 12 }}>
                <label htmlFor="verify-email">E-mail</label>
                <input
                  id="verify-email"
                  type="email"
                  required
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                />
              </div>
              <div className="form-group" style={{ marginBottom: 16 }}>
                <label htmlFor="reset-code">Código de 6 dígitos</label>
                <input
                  id="reset-code"
                  type="text"
                  inputMode="numeric"
                  maxLength={6}
                  required
                  value={code}
                  placeholder="123456"
                  onChange={(e) => setCode(e.target.value.replace(/\D/g, '').slice(0, 6))}
                />
              </div>
              <div style={{ display: 'grid', gap: 10 }}>
                <button type="submit" className="btn-primary" disabled={loading} style={{ width: '100%' }}>
                  {loading ? 'Validando...' : 'Validar código'}
                </button>
                <button type="button" className="btn-secondary" onClick={() => setStep(1)} disabled={loading} style={{ width: '100%' }}>
                  Alterar e-mail / reenviar código
                </button>
              </div>
            </form>
          )}

          {step === 3 && (
            <form onSubmit={handleResetPassword}>
              <div className="form-group" style={{ marginBottom: 12 }}>
                <label htmlFor="final-email">E-mail</label>
                <input id="final-email" type="email" required value={email} onChange={(e) => setEmail(e.target.value)} />
              </div>
              <div className="form-group" style={{ marginBottom: 12 }}>
                <label htmlFor="final-code">Código validado</label>
                <input
                  id="final-code"
                  type="text"
                  inputMode="numeric"
                  maxLength={6}
                  required
                  value={code}
                  onChange={(e) => setCode(e.target.value.replace(/\D/g, '').slice(0, 6))}
                />
              </div>
              <div className="form-group" style={{ marginBottom: 12 }}>
                <label htmlFor="new-password">Nova senha</label>
                <input
                  id="new-password"
                  type="password"
                  required
                  value={newPassword}
                  placeholder="Digite sua nova senha"
                  onChange={(e) => setNewPassword(e.target.value)}
                />
              </div>
              <div className="form-group" style={{ marginBottom: 16 }}>
                <label htmlFor="confirm-password">Confirmar nova senha</label>
                <input
                  id="confirm-password"
                  type="password"
                  required
                  value={confirmPassword}
                  placeholder="Repita sua nova senha"
                  onChange={(e) => setConfirmPassword(e.target.value)}
                />
              </div>
              <div style={{ display: 'grid', gap: 10 }}>
                <button type="submit" className="btn-primary" disabled={loading} style={{ width: '100%' }}>
                  {loading ? 'Salvando nova senha...' : 'Salvar nova senha'}
                </button>
                <button type="button" className="btn-secondary" onClick={() => setStep(2)} disabled={loading} style={{ width: '100%' }}>
                  Voltar para o código
                </button>
              </div>
            </form>
          )}

          <div style={{ marginTop: 16, textAlign: 'center' }}>
            <button
              type="button"
              onClick={() => navigate('/login', { replace: true, state: { email } })}
              style={{ background: 'none', border: 'none', color: '#0369a1', cursor: 'pointer', textDecoration: 'underline', fontSize: 13 }}
            >
              Voltar para login
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
