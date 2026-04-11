import axios from 'axios'

const API_BASE_URL = '/api'

const api = axios.create({
  baseURL: API_BASE_URL,
  headers: {
    'Content-Type': 'application/json',
  },
})

// Produtos
export const produtoService = {
  listar: () => api.get('/produtos'),
  obter: (id) => api.get(`/produtos/${id}`),
  criar: (dados) => api.post('/produtos', dados),
  atualizar: (id, dados) => api.put(`/produtos/${id}`, dados),
  deletar: (id) => api.delete(`/produtos/${id}`),
  criarEmMassa: (dados) => api.post('/produtos/em-massa/criar', dados),
  editarEmMassa: (dados) => api.post('/produtos/em-massa/editar', dados),
  deletarEmMassa: (skus) => api.post('/produtos/em-massa/deletar', skus),
  atualizarEstoqueEmMassa: (dados) => api.post('/produtos/estoque/atualizar-em-massa', dados),
  atualizarSkuEmMassa: (dados) => api.post('/produtos/sku/atualizar-em-massa', dados),
  gerenciarComponentes: (sku, dados) => api.post(`/produtos/${sku}/componentes`, dados),
  obterEstoque: (sku) => api.get(`/produtos/estoque/${sku}`),
}

// CSV
export const csvService = {
  upload: (file) => {
    const formData = new FormData()
    formData.append('file', file)
    return api.post('/csv/upload', formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
    })
  },
  importar: (tipoOperacao, ignorarErros = false) =>
    api.post(`/csv/importar?tipo_operacao=${tipoOperacao}&ignorar_erros=${ignorarErros}`),
  exportar: (tipo, filtros) => api.post('/csv/exportar', { tipo, filtros }),
  listarUploads: () => api.get('/csv/uploads'),
  listarExports: () => api.get('/csv/exports'),
  gerarTemplate: (tipo) => api.post(`/csv/template/${tipo}`),
  deletarUpload: (nome) => api.delete(`/csv/upload/${nome}`),
  deletarExport: (nome) => api.delete(`/csv/export/${nome}`),
}

// Configuração
export const configService = {
  verificarSaude: () => api.get('/health'),
  obterConfig: () => api.get('/config'),
  validarBling: () => api.post('/bling/validar'),
  configurarBling: (apiKey) => api.post('/bling/configurar', { api_key: apiKey }),
}

export default api
