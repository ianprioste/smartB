import React from 'react';

export class ErrorBoundary extends React.Component {
  constructor(props) {
    super(props);
    this.state = { hasError: false, error: null, errorInfo: null };
  }

  static getDerivedStateFromError(error) {
    return { hasError: true, error };
  }

  componentDidCatch(error, errorInfo) {
    this.setState({ errorInfo });
    console.error('[ErrorBoundary] Caught error:', error, errorInfo);
  }

  render() {
    if (this.state.hasError) {
      return (
        <div style={{ padding: 32, maxWidth: 700, margin: '40px auto', fontFamily: 'system-ui, sans-serif' }}>
          <div style={{ background: '#fef2f2', border: '1px solid #fca5a5', borderRadius: 12, padding: 24 }}>
            <h2 style={{ color: '#991b1b', margin: '0 0 12px 0', fontSize: 18 }}>Erro ao carregar a página</h2>
            <p style={{ color: '#7f1d1d', margin: '0 0 16px 0', fontSize: 14 }}>
              Ocorreu um erro inesperado. Por favor, tente recarregar a página.
            </p>
            <details style={{ marginBottom: 16 }}>
              <summary style={{ cursor: 'pointer', color: '#991b1b', fontWeight: 600, fontSize: 13 }}>
                Detalhes do erro
              </summary>
              <pre style={{ marginTop: 8, padding: 12, background: '#fff', borderRadius: 8, fontSize: 12, overflow: 'auto', color: '#334155', border: '1px solid #e2e8f0' }}>
                {this.state.error?.toString()}
                {'\n\n'}
                {this.state.errorInfo?.componentStack}
              </pre>
            </details>
            <button
              onClick={() => window.location.reload()}
              style={{ padding: '8px 20px', borderRadius: 8, border: 'none', background: '#991b1b', color: '#fff', fontWeight: 600, cursor: 'pointer', fontSize: 14 }}
            >
              Recarregar página
            </button>
          </div>
        </div>
      );
    }

    return this.props.children;
  }
}
