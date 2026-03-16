import { useState, useEffect } from 'react';

const API_BASE = '/api';

/**
 * Hook para gerenciar estado do wizard de novo cadastro
 * Encapsula toda a lógica de geração de planos
 */
export function useWizard() {
  const [step, setStep] = useState(1);
  const [models, setModels] = useState([]);
  const [colors, setColors] = useState([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  // Print Info (Step 1)
  const [printInfo, setPrintInfo] = useState({
    code: '',
    name: '',
  });

  // Models (Step 2)
  const [selectedModels, setSelectedModels] = useState([]);

  // Colors (Step 3)
  const [selectedColors, setSelectedColors] = useState([]);

  // Overrides
  const [overrides, setOverrides] = useState({
    short_description: '',
    complement_description: '',
    complement_same_as_short: true,
    category_override_id: '',
  });

  // Plan & Execution
  const [plan, setPlan] = useState(null);
  const [generatingPlan, setGeneratingPlan] = useState(false);
  const [loadingStatus, setLoadingStatus] = useState('');

  /**
   * Busca modelos e cores do backend
   */
  async function fetchConfiguration() {
    try {
      setLoading(true);
      const [modelsResp, colorsResp] = await Promise.all([
        fetch(`${API_BASE}/config/models`),
        fetch(`${API_BASE}/config/colors`),
      ]);

      if (!modelsResp.ok || !colorsResp.ok) {
        throw new Error('Failed to fetch configuration');
      }

      const modelsData = await modelsResp.json();
      const colorsData = await colorsResp.json();

      const activeModels = modelsData.filter(m => m.is_active);
      const activeColors = colorsData.filter(c => c.is_active);

      setModels(activeModels);
      setColors(activeColors);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }

  /**
   * Toggle modelo selecionado
   */
  function handleModelToggle(model) {
    const isSelected = selectedModels.find(m => m.code === model.code);
    if (isSelected) {
      setSelectedModels(selectedModels.filter(m => m.code !== model.code));
    } else {
      setSelectedModels([
        ...selectedModels,
        {
          code: model.code,
          name: model.name,
          allowed_sizes: model.allowed_sizes,
          selected_sizes: [...model.allowed_sizes],
          price: '',
        },
      ]);
    }
  }

  /**
   * Toggle tamanho de modelo
   */
  function handleSizeToggle(modelCode, size) {
    setSelectedModels(
      selectedModels.map(m => {
        if (m.code === modelCode) {
          const isSelected = m.selected_sizes.includes(size);
          return {
            ...m,
            selected_sizes: isSelected
              ? m.selected_sizes.filter(s => s !== size)
              : [...m.selected_sizes, size],
          };
        }
        return m;
      })
    );
  }

  /**
   * Muda preço de modelo
   */
  function handlePriceChange(modelCode, value) {
    setSelectedModels(
      selectedModels.map(m =>
        m.code === modelCode ? { ...m, price: value } : m
      )
    );
  }

  /**
   * Toggle cor selecionada
   */
  function handleColorToggle(colorCode) {
    if (selectedColors.includes(colorCode)) {
      setSelectedColors(selectedColors.filter(c => c !== colorCode));
    } else {
      setSelectedColors([...selectedColors, colorCode]);
    }
  }

  /**
   * Gera payload do plano
   */
  function buildPlanPayload(autoSeedBasePlain = false) {
    return {
      print: {
        code: printInfo.code.toUpperCase(),
        name: printInfo.name,
      },
      models: selectedModels.map(m => ({
        code: m.code,
        sizes: m.selected_sizes,
        price: parseFloat(m.price),
      })),
      colors: selectedColors,
      overrides: {
        short_description: overrides.short_description || null,
        complement_description: overrides.complement_same_as_short
          ? null
          : overrides.complement_description || null,
        complement_same_as_short: overrides.complement_same_as_short,
        category_override_id: overrides.category_override_id
          ? parseInt(overrides.category_override_id, 10)
          : null,
      },
      options: {
        auto_seed_base_plain: autoSeedBasePlain,
      },
    };
  }

  /**
   * Envia requisição para gerar plano
   */
  async function generatePlan(autoSeedBasePlain = false) {
    const payload = buildPlanPayload(autoSeedBasePlain);

    const resp = await fetch(`${API_BASE}/plans/new`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    });

    if (!resp.ok) {
      const errorData = await resp.json();

      // Check for token expiration
      if (resp.status === 401 && errorData.detail?.code === 'BLING_TOKEN_EXPIRED') {
        const error = new Error('Token expirado');
        error.code = 'BLING_TOKEN_EXPIRED';
        error.status = 401;
        throw error;
      }

      throw new Error(errorData.detail?.message || 'Falha ao gerar plano');
    }

    return await resp.json();
  }

  /**
   * Valida dados atuais do wizard
   */
  function validateStep(stepNum) {
    switch (stepNum) {
      case 1:
        if (!printInfo.code || !printInfo.name) {
          setError('Preencha código e nome da estampa');
          return false;
        }
        return true;

      case 2:
        if (selectedModels.length === 0) {
          setError('Selecione pelo menos um modelo');
          return false;
        }

        for (const model of selectedModels) {
          if (!parseFloat(model.price) || parseFloat(model.price) <= 0) {
            setError(`Informe preço válido para o modelo ${model.code}`);
            return false;
          }

          if (model.selected_sizes.length === 0) {
            setError(`Modelo ${model.code} não tem tamanhos selecionados`);
            return false;
          }
        }
        return true;

      case 3:
        if (selectedColors.length === 0) {
          setError('Selecione pelo menos uma cor');
          return false;
        }
        return true;

      default:
        return false;
    }
  }

  /**
   * Avança para próximo passo
   */
  function nextStep() {
    if (validateStep(step)) {
      setStep(step + 1);
      setError(null);
    }
  }

  /**
   * Volta para passo anterior
   */
  function previousStep() {
    if (step > 1) {
      setStep(step - 1);
      setError(null);
    }
  }

  /**
   * Reseta todo o wizard
   */
  function reset() {
    setStep(1);
    setPrintInfo({ code: '', name: '' });
    setSelectedModels([]);
    setSelectedColors([]);
    setOverrides({
      short_description: '',
      complement_description: '',
      complement_same_as_short: true,
      category_override_id: '',
    });
    setPlan(null);
    setError(null);
  }

  useEffect(() => {
    fetchConfiguration();
  }, []);

  return {
    // State
    step,
    models,
    colors,
    loading,
    error,
    printInfo,
    selectedModels,
    selectedColors,
    overrides,
    plan,
    generatingPlan,
    loadingStatus,

    // Setters
    setError,
    setPlan,
    setGeneratingPlan,
    setLoadingStatus,
    setPrintInfo,
    setOverrides,

    // Methods
    fetchConfiguration,
    handleModelToggle,
    handleSizeToggle,
    handlePriceChange,
    handleColorToggle,
    buildPlanPayload,
    generatePlan,
    validateStep,
    nextStep,
    previousStep,
    reset,
  };
}
