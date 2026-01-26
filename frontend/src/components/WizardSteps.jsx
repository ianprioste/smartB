import React from 'react';

/**
 * Step 1: Informações da Estampa
 */
export function Step1PrintInfo({ printInfo, setPrintInfo, overrides, setOverrides }) {
  return (
    <div className="wizard-content">
      <h2>📝 Dados da Estampa</h2>
      <div className="form-group">
        <label>Código da Estampa *</label>
        <input
          type="text"
          value={printInfo.code}
          onChange={(e) =>
            setPrintInfo({ ...printInfo, code: e.target.value.toUpperCase() })
          }
          placeholder="Ex: STPV"
          maxLength={20}
        />
      </div>
      <div className="form-group">
        <label>Nome da Estampa *</label>
        <input
          type="text"
          value={printInfo.name}
          onChange={(e) => setPrintInfo({ ...printInfo, name: e.target.value })}
          placeholder="Ex: Santa Teresinha Pequena Via"
        />
      </div>
      <div className="form-grid">
        <div className="form-group">
          <label>Descrição Curta (opcional)</label>
          <textarea
            value={overrides.short_description}
            onChange={(e) =>
              setOverrides({ ...overrides, short_description: e.target.value })
            }
            placeholder="Ex: Santa Teresinha | Camiseta | Marca"
            rows={2}
          />
        </div>
        <div className="form-group">
          <label>
            <input
              type="checkbox"
              checked={overrides.complement_same_as_short}
              onChange={(e) =>
                setOverrides({
                  ...overrides,
                  complement_same_as_short: e.target.checked,
                  ...(e.target.checked ? { complement_description: '' } : {}),
                })
              }
            />{' '}
            Usar descrição curta também como complementar
          </label>
          {!overrides.complement_same_as_short && (
            <textarea
              value={overrides.complement_description}
              onChange={(e) =>
                setOverrides({
                  ...overrides,
                  complement_description: e.target.value,
                })
              }
              placeholder="Descrição complementar"
              rows={2}
            />
          )}
        </div>
        <div className="form-group">
          <label>Categoria (ID) opcional</label>
          <input
            type="number"
            value={overrides.category_override_id}
            onChange={(e) =>
              setOverrides({
                ...overrides,
                category_override_id: e.target.value,
              })
            }
            placeholder="ID da categoria no Bling"
            min="0"
          />
          <small>Deixe em branco para manter a categoria do template</small>
        </div>
      </div>
    </div>
  );
}

/**
 * Step 2: Seleção de Modelos e Tamanhos
 */
export function Step2Models({
  models,
  selectedModels,
  onModelToggle,
  onSizeToggle,
  onPriceChange,
}) {
  return (
    <div className="wizard-content">
      <h2>📐 Selecione os Modelos e Tamanhos</h2>
      {models.length === 0 ? (
        <div className="wizard-error">
          ⚠️ Nenhum modelo disponível. Por favor, crie modelos primeiro.
        </div>
      ) : (
        <div className="models-grid">
          {models.map((model) => {
            const selected = selectedModels.find((m) => m.code === model.code);
            return (
              <div
                key={model.code}
                className={`model-card ${selected ? 'selected' : ''}`}
              >
                <div
                  className="model-header"
                  onClick={() => onModelToggle(model)}
                >
                  <input type="checkbox" checked={!!selected} readOnly />
                  <strong>{model.code}</strong> - {model.name}
                </div>
                {selected && (
                  <div className="sizes-selection">
                    <label>Tamanhos:</label>
                    <div className="sizes-buttons">
                      {model.allowed_sizes.map((size) => (
                        <button
                          key={size}
                          className={`size-btn ${
                            selected.selected_sizes.includes(size)
                              ? 'active'
                              : ''
                          }`}
                          onClick={() => onSizeToggle(model.code, size)}
                        >
                          {size}
                        </button>
                      ))}
                    </div>
                    <div className="form-group inline">
                      <label>Preço (R$)</label>
                      <input
                        type="number"
                        step="0.01"
                        min="0"
                        value={selected.price}
                        onClick={(e) => e.stopPropagation()}
                        onChange={(e) =>
                          onPriceChange(model.code, e.target.value)
                        }
                        placeholder="Ex: 79.90"
                      />
                    </div>
                  </div>
                )}
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}

/**
 * Step 3: Seleção de Cores
 */
export function Step3Colors({ colors, selectedColors, onColorToggle }) {
  return (
    <div className="wizard-content">
      <h2>🎨 Selecione as Cores</h2>
      <div className="colors-grid">
        {colors.map((color) => (
          <div
            key={color.code}
            className={`color-card ${
              selectedColors.includes(color.code) ? 'selected' : ''
            }`}
            onClick={() => onColorToggle(color.code)}
          >
            <input
              type="checkbox"
              checked={selectedColors.includes(color.code)}
              readOnly
            />
            <strong>{color.code}</strong> - {color.name}
          </div>
        ))}
      </div>
    </div>
  );
}

/**
 * Progress bar do wizard
 */
export function WizardProgress({ currentStep }) {
  const steps = [
    { num: 1, label: 'Estampa' },
    { num: 2, label: 'Modelos' },
    { num: 3, label: 'Cores' },
    { num: 4, label: 'Preview' },
  ];

  return (
    <div className="wizard-progress">
      {steps.map((step) => (
        <div
          key={step.num}
          className={`wizard-step ${currentStep >= step.num ? 'active' : ''} ${
            currentStep > step.num ? 'completed' : ''
          }`}
        >
          {step.num}. {step.label}
        </div>
      ))}
    </div>
  );
}

/**
 * Botões de navegação do wizard
 */
export function WizardNavigation({
  step,
  canProceed,
  onPrevious,
  onNext,
  onGeneratePlan,
  generating,
}) {
  if (step >= 4) return null;

  return (
    <div className="wizard-actions">
      {step > 1 && (
        <button className="btn-secondary" onClick={onPrevious}>
          ← Anterior
        </button>
      )}
      {step < 3 && (
        <button
          className="btn-primary"
          onClick={onNext}
          disabled={!canProceed}
        >
          Próximo →
        </button>
      )}
      {step === 3 && (
        <button
          className="btn-primary"
          onClick={onGeneratePlan}
          disabled={!canProceed || generating}
        >
          {generating ? 'Gerando Preview...' : '🔍 Gerar Preview'}
        </button>
      )}
    </div>
  );
}
