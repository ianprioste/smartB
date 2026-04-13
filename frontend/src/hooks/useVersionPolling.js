import { useEffect, useRef } from 'react';

/**
 * Hook para sincronização baseada em versão (polling).
 * 
 * Detecta mudanças de versão no servidor em intervalos regulares.
 * Quando habilitado, faz polling da versão atual, detecta mudanças,
 * e chama callback para buscar delta. Adapta intervalo baseado em
 * visibilidade da aba (ativo vs oculto).
 * 
 * @param {Object} config - Configuração
 * @param {boolean} config.enabled - Se polling deve estar ativo
 * @param {string} config.pollKey - Chave única do poller (p.ex. 'orders_global')
 * @param {Function} config.fetchVersion - async () => version | null
 * @param {Function} config.onVersionChange - async () => void, chamado na mudança
 * @param {number} config.intervalMsActive - Intervalo quando aba ativa (ms)
 * @param {number} config.intervalMsHidden - Intervalo quando aba oculta (ms)
 */
export function useVersionPolling({
  enabled = true,
  pollKey = 'default',
  fetchVersion,
  onVersionChange,
  intervalMsActive = 7000,
  intervalMsHidden = 15000,
}) {
  // Cache de versão por pollKey (usamos ref compartilhada entre renders)
  const versionCacheRef = useRef(new Map());
  const intervalRef = useRef(null);
  const isPollingRef = useRef(false);

  // Função para rodar uma iteração de polling
  const poll = async () => {
    if (isPollingRef.current || !enabled) return;

    isPollingRef.current = true;
    try {
      const newVersion = await fetchVersion();

      // Se fetchVersion retorna null, skip (erro ou indisponível)
      if (newVersion === null || newVersion === undefined) {
        isPollingRef.current = false;
        return;
      }

      const cache = versionCacheRef.current;
      const previousVersion = cache.get(pollKey);

      // Atualizar cache com nova versão
      cache.set(pollKey, newVersion);

      // Se há versão prévia e mudou, chamar callback
      if (previousVersion !== undefined && previousVersion !== newVersion) {
        await onVersionChange();
      }
    } catch (err) {
      // Log silencioso, retry no próximo ciclo
      console.debug(`[useVersionPolling] poll error for ${pollKey}:`, err);
    } finally {
      isPollingRef.current = false;
    }
  };

  // Função para iniciar/reiniciar polling com intervalo correto
  const startPolling = async () => {
    // Fazer poll imediato para inicializar versão cache
    await poll();

    // Limpar intervalo anterior se houver
    if (intervalRef.current) {
      clearInterval(intervalRef.current);
    }

    // Detectar intervalo baseado em visibilidade da aba
    const getInterval = () => {
      if (typeof document === 'undefined') return intervalMsActive;
      return document.hidden ? intervalMsHidden : intervalMsActive;
    };

    // Rodar polling inicial
    let currentInterval = getInterval();
    intervalRef.current = setInterval(async () => {
      // Trocar intervalo se visibilidade mudou
      const newInterval = getInterval();
      if (newInterval !== currentInterval) {
        currentInterval = newInterval;
        // Reiniciar intervalo com novo valor
        if (intervalRef.current) {
          clearInterval(intervalRef.current);
        }
        intervalRef.current = setInterval(poll, currentInterval);
      }

      await poll();
    }, currentInterval);
  };

  // Função para parar polling
  const stopPolling = () => {
    if (intervalRef.current) {
      clearInterval(intervalRef.current);
      intervalRef.current = null;
    }
  };

  // Efeito principal para controlar ciclo de vida
  useEffect(() => {
    if (!enabled) {
      stopPolling();
      return;
    }

    startPolling();

    return () => {
      stopPolling();
    };
  }, [enabled, pollKey, intervalMsActive, intervalMsHidden, fetchVersion, onVersionChange]);
}
