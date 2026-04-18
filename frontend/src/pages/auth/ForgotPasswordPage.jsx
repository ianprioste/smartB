import React, { useEffect, useRef, useState } from 'react';
import { useLocation, useNavigate } from 'react-router-dom';

const API_BASE = '/api';
const CODE_LENGTH = 6;

const cardStyle = {
  width: '100%',
  maxWidth: 420,
  background: '#ffffff',
  borderRadius: 16,
  boxShadow: '0 20px 50px rgba(15, 23, 42, 0.08)',
  border: '1px solid #e2e8f0',
};

const wrapperStyle = {
  minHeight: '100vh',
  display: 'grid',
  placeItems: 'center',
  background: 'linear-gradient(135deg, #f8fafc 0%, #e2e8f0 100%)',
  padding: 16,
};

export function ForgotPasswordPage() {
  const navigate = useNavigate();
  const location = useLocation();

  const [step, setStep] = useState('email'); // email | code | reset | done
  const [email, setEmail] = useState('');
  const [code, setCode] = useState('');
  const [newPassword, setNewPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [countdown, setCountdown] = useState(0);
  const [canResend, setCanResend] = useState(false);
  const timerRef = useRef(null);

  useEffect(() => {
    const stateEmail = location.state?.email;
    if (typeof stateEmail === 'string' && stateEmail) {
      setEmail(stateEmail);
    }
  }, [location.state]);

  useEffect(() => {
    return () => {
      if (timerRef.current) clearInterval(timerRef.current);
    };
  }, []);

  function startCountdown(seconds) {
    setCountdown(seconds);
    setCanResend(false);
    if (timerRef.current) clearInterval(timerRef.current);
    timerRef.current = setInterval(() => {
      setCountdown((prev) => {
        if (prev <= 1) {
          clearInterval(timerRef.current);
          timerRef.current = null;
          setCanResend(true);
          return 0;
        }
        return prev - 1;
      });
    }, 1000);
  }

  function formatCountdown(secs) {
    const m = Math.floor(secs / 60);
    const s = secs % 60;
    return `${m}:${String(s).padStart(2, '0')}`;
  }

  async function handleRequestCode(e) {
    e.preventDefault();
    setError('');
    setLoading(true);
    try {
      const resp = await fetch(`${API_BASE}/auth/access/forgot-password/request`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        credentials: 'include',
        body: JSON.stringify({ email: email.trim().toLowerCase() }),
      });
      const data = await resp.json().catch(() => ({}));
      if (!resp.ok) {
        throw new Error(data.detail || 'Falha ao solicitar código');
      }
      setStep('code');
      setCode('');
      startCountdown(300);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }

  async function handleResendCode() {
    setError('');
    setLoading(true);
    try {
      const resp = await fetch(`${API_BASE}/auth/access/forgot-password/request`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        credentials: 'include',
        body: JSON.stringify({ email: email.trim().toLowerCase() }),
      });
      const data = await resp.json().catch(() => ({}));
      if (!resp.ok) {
        throw new Error(data.detail || 'Falha ao reenviar código');
      }
      setCode('');
      startCountdown(300);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }

  async function handleVerifyCode(e) {
    e.preventDefault();
    setError('');
    if (code.length !== CODE_LENGTH) {
      setError(`Digite o código de ${CODE_LENGTH} dígitos`);
      return;
    }
    setLoading(true);
    try {
      const resp = await fetch(`${API_BASE}/auth/access/forgot-password/verify`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        credentials: 'include',
        body: JSON.stringify({ email: email.trim().toLowerCase(), code }),
      });
      const data = await resp.json().catch(() => ({}));
      if (!resp.ok) {
        throw new Error(data.detail || 'Código inválido ou expirado');
      }
      setStep('reset');
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }

  async function handleResetPassword(e) {
    e.preventDefault();
    setError('');
    if (newPassword.length < 6) {
      setError('A senha deve ter pelo menos 6 caracteres');
      return;
    }
    if (newPassword !== confirmPassword) {
      setError('As senhas não coincidem');
      return;
    }
    setLoading(true);
    try {
      const resp = await fetch(`${API_BASE}/auth/access/forgot-password/reset`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        credentials: 'include',
        body: JSON.stringify({
          email: email.trim().toLowerCase(),
          code,
          new_password: newPassword,
        }),
      });
      const data = await resp.json().catch(() => ({}));
      if (!resp.ok) {
        throw new Error(data.detail || 'Falha ao redefinir senha');
      }
      setStep('done');
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }

  const backToLogin = (
    <div style={{ marginTop: 16, textAlign: 'center' }}>
      <button
        type="button"
        onClick={() => navigate('/login')}
        style={{ background: 'none', border: 'none', color: '#0369a1', cursor: 'pointer', textDecoration: 'underline', fontSize: 13, padding: 0 }}
      >
        Voltar ao login
      </button>
    </div>
  );

  // Step 1: Email
  if (step === 'email') {
    return (
      <div style={wrapperStyle}>
        <div style={cardStyle}>
          <div style={{ padding: 24, borderBottom: '1px solid #e2e8f0' }}>
            <h2 style={{ margin: 0, color: '#0f172a' }}>Recuperar Senha</h2>
            <p style={{ margin: '6px 0 0', color: '#64748b', fontSize: 14 }}>
              Informe seu e-mail para receber um código de verificação
            </p>
          </div>
          <form onSubmit={handleRequestCode} style={{ padding: 24 }}>
            <div className="form-group" style={{ marginBottom: 16 }}>
              <label htmlFor="reset-email">E-mail</label>
              <input
                id="reset-email"
                type="email"
                required
                value={email}
                placeholder="nome@empresa.com"
                onChange={(e) => setEmail(e.target.value)}
                autoFocus
              />
            </div>
            {error && <div className="error" style={{ marginBottom: 12 }}>{error}</div>}
            <button type="submit" className="btn-primary" disabled={loading} style={{ width: '100%' }}>
              {loading ? 'Enviando...' : 'Enviar código'}
            </button>
            {backToLogin}
          </form>
        </div>
      </div>
    );
  }

  // Step 2: Code verification
  if (step === 'code') {
    return (
      <div style={wrapperStyle}>
        <div style={cardStyle}>
          <div style={{ padding: 24, borderBottom: '1px solid #e2e8f0' }}>
            <h2 style={{ margin: 0, color: '#0f172a' }}>Verificar Código</h2>
            <p style={{ margin: '6px 0 0', color: '#64748b', fontSize: 14 }}>
              Digite o código de {CODE_LENGTH} dígitos enviado para <strong>{email}</strong>
            </p>
          </div>
          <form onSubmit={handleVerifyCode} style={{ padding: 24 }}>
            <div className="form-group" style={{ marginBottom: 16 }}>
              <label htmlFor="reset-code">Código</label>
              <input
                id="reset-code"
                type="text"
                inputMode="numeric"
                pattern="[0-9]*"
                maxLength={CODE_LENGTH}
                required
                value={code}
                placeholder="000000"
                onChange={(e) => setCode(e.target.value.replace(/\D/g, '').slice(0, CODE_LENGTH))}
                style={{ fontSize: 24, letterSpacing: 8, textAlign: 'center', fontFamily: 'monospace' }}
                autoFocus
                autoComplete="one-time-code"
              />
            </div>
            {countdown > 0 && (
              <p style={{ fontSize: 13, color: '#64748b', textAlign: 'center', margin: '0 0 12px' }}>
                Código expira em <strong>{formatCountdown(countdown)}</strong>
              </p>
            )}
            {canResend && (
              <p style={{ fontSize: 13, textAlign: 'center', margin: '0 0 12px' }}>
                <button
                  type="button"
                  onClick={handleResendCode}
                  disabled={loading}
                  style={{ background: 'none', border: 'none', color: '#0369a1', cursor: 'pointer', textDecoration: 'underline', fontSize: 13, padding: 0 }}
                >
                  Reenviar código
                </button>
              </p>
            )}
            {error && <div className="error" style={{ marginBottom: 12 }}>{error}</div>}
            <button type="submit" className="btn-primary" disabled={loading || code.length !== CODE_LENGTH} style={{ width: '100%' }}>
              {loading ? 'Verificando...' : 'Verificar'}
            </button>
            {backToLogin}
          </form>
        </div>
      </div>
    );
  }

  // Step 3: New password
  if (step === 'reset') {
    return (
      <div style={wrapperStyle}>
        <div style={cardStyle}>
          <div style={{ padding: 24, borderBottom: '1px solid #e2e8f0' }}>
            <h2 style={{ margin: 0, color: '#0f172a' }}>Nova Senha</h2>
            <p style={{ margin: '6px 0 0', color: '#64748b', fontSize: 14 }}>
              Defina sua nova senha (mínimo 6 caracteres)
            </p>
          </div>
          <form onSubmit={handleResetPassword} style={{ padding: 24 }}>
            <div className="form-group" style={{ marginBottom: 16 }}>
              <label htmlFor="new-password">Nova senha</label>
              <input
                id="new-password"
                type="password"
                required
                minLength={6}
                value={newPassword}
                placeholder="Digite a nova senha"
                onChange={(e) => setNewPassword(e.target.value)}
                autoFocus
              />
            </div>
            <div className="form-group" style={{ marginBottom: 16 }}>
              <label htmlFor="confirm-password">Confirmar senha</label>
              <input
                id="confirm-password"
                type="password"
                required
                minLength={6}
                value={confirmPassword}
                placeholder="Confirme a nova senha"
                onChange={(e) => setConfirmPassword(e.target.value)}
              />
            </div>
            {error && <div className="error" style={{ marginBottom: 12 }}>{error}</div>}
            <button type="submit" className="btn-primary" disabled={loading} style={{ width: '100%' }}>
              {loading ? 'Redefinindo...' : 'Redefinir senha'}
            </button>
            {backToLogin}
          </form>
        </div>
      </div>
    );
  }

  // Step 4: Success
  return (
    <div style={wrapperStyle}>
      <div style={cardStyle}>
        <div style={{ padding: 24, borderBottom: '1px solid #e2e8f0' }}>
          <h2 style={{ margin: 0, color: '#0f172a' }}>Senha Redefinida</h2>
        </div>
        <div style={{ padding: 24, textAlign: 'center' }}>
          <div style={{ fontSize: 48, marginBottom: 12 }}>&#10003;</div>
          <p style={{ color: '#0f172a', fontSize: 15, margin: '0 0 20px' }}>
            Sua senha foi alterada com sucesso.
          </p>
          <button
            type="button"
            className="btn-primary"
            style={{ width: '100%' }}
            onClick={() => navigate('/login', { state: { email, resetSuccess: 'Senha redefinida. Faça login com sua nova senha.' } })}
          >
            Ir para o login
          </button>
        </div>
      </div>
    </div>
  );
}
