import { Card, Tabs, Button, Space, Upload, Table, message, Modal, Spin, Select, Alert } from 'antd'
import { UploadOutlined, DownloadOutlined, DeleteOutlined } from '@ant-design/icons'
import { useQuery } from 'react-query'
import { useState } from 'react'
import { csvService } from '../services/api'

export default function ImportarExportar() {
  const { data: uploads, isLoading: uploadsLoading, refetch: refetchUploads } = useQuery('uploads', () => csvService.listarUploads())
  const { data: exports_, isLoading: exportsLoading, refetch: refetchExports } = useQuery('exports', () => csvService.listarExports())
  const [tipoOperacao, setTipoOperacao] = useState('adicionar')
  const [processando, setProcessando] = useState(false)

  const uploadColumns = [
    {
      title: 'Nome do Arquivo',
      dataIndex: 'nome',
      key: 'nome',
    },
    {
      title: 'Tamanho',
      dataIndex: 'tamanho',
      key: 'tamanho',
      render: (text) => `${(text / 1024).toFixed(2)} KB`,
    },
    {
      title: 'Modificado',
      dataIndex: 'modificado',
      key: 'modificado',
      render: (text) => new Date(text * 1000).toLocaleDateString(),
    },
    {
      title: 'Ações',
      key: 'acoes',
      render: (_, record) => (
        <Space>
          <Button
            type="primary"
            onClick={() => {
              Modal.confirm({
                title: 'Confirmar Importação',
                content: `Deseja importar o arquivo ${record.nome} com a operação "${tipoOperacao}"?`,
                okText: 'Sim',
                cancelText: 'Não',
                onOk: async () => {
                  setProcessando(true)
                  try {
                    await csvService.importar(tipoOperacao)
                    message.success('Arquivo importado com sucesso')
                    refetchUploads()
                  } catch (error) {
                    message.error('Erro ao importar arquivo')
                  } finally {
                    setProcessando(false)
                  }
                },
              })
            }}
          >
            Importar
          </Button>
          <Button
            danger
            onClick={() => {
              Modal.confirm({
                title: 'Confirmar Exclusão',
                content: `Deseja deletar o arquivo ${record.nome}?`,
                okText: 'Sim',
                cancelText: 'Não',
                onOk: async () => {
                  try {
                    await csvService.deletarUpload(record.nome)
                    message.success('Arquivo deletado com sucesso')
                    refetchUploads()
                  } catch (error) {
                    message.error('Erro ao deletar arquivo')
                  }
                },
              })
            }}
          >
            Deletar
          </Button>
        </Space>
      ),
    },
  ]

  const exportColumns = [
    {
      title: 'Nome do Arquivo',
      dataIndex: 'nome',
      key: 'nome',
    },
    {
      title: 'Tamanho',
      dataIndex: 'tamanho',
      key: 'tamanho',
      render: (text) => `${(text / 1024).toFixed(2)} KB`,
    },
    {
      title: 'Modificado',
      dataIndex: 'modificado',
      key: 'modificado',
      render: (text) => new Date(text * 1000).toLocaleDateString(),
    },
    {
      title: 'Ações',
      key: 'acoes',
      render: (_, record) => (
        <Button
          danger
          onClick={() => {
            Modal.confirm({
              title: 'Confirmar Exclusão',
              content: `Deseja deletar o arquivo ${record.nome}?`,
              okText: 'Sim',
              cancelText: 'Não',
              onOk: async () => {
                try {
                  await csvService.deletarExport(record.nome)
                  message.success('Arquivo deletado com sucesso')
                  refetchExports()
                } catch (error) {
                  message.error('Erro ao deletar arquivo')
                }
              },
            })
          }}
        >
          Deletar
        </Button>
      ),
    },
  ]

  const tabsItems = [
    {
      key: 'importar',
      label: 'Importar',
      children: (
        <Card loading={uploadsLoading}>
          <Space direction="vertical" style={{ width: '100%' }} size="large">
            <Alert
              message="Selecione o tipo de operação e faça upload do arquivo CSV"
              type="info"
              showIcon
            />

            <div>
              <label style={{ marginBottom: 8, display: 'block' }}>Tipo de Operação</label>
              <Select
                value={tipoOperacao}
                onChange={setTipoOperacao}
                style={{ width: '100%' }}
                options={[
                  { label: 'Adicionar Produtos', value: 'adicionar' },
                  { label: 'Editar Produtos', value: 'editar' },
                  { label: 'Deletar Produtos', value: 'deletar' },
                  { label: 'Atualizar Estoque', value: 'atualizar_estoque' },
                  { label: 'Atualizar SKU', value: 'atualizar_sku' },
                ]}
              />
            </div>

            <Upload
              action="/api/csv/upload"
              accept=".csv"
              maxCount={1}
              onSuccess={() => {
                message.success('Arquivo enviado com sucesso')
                refetchUploads()
              }}
              onError={() => {
                message.error('Erro ao enviar arquivo')
              }}
            >
              <Button icon={<UploadOutlined />}>Upload CSV</Button>
            </Upload>

            <div>
              <h3>Arquivos Enviados</h3>
              <Spin spinning={uploadsLoading}>
                <Table
                  columns={uploadColumns}
                  dataSource={uploads?.arquivos || []}
                  rowKey="nome"
                  pagination={false}
                />
              </Spin>
            </div>
          </Space>
        </Card>
      ),
    },
    {
      key: 'exportar',
      label: 'Exportar',
      children: (
        <Card loading={exportsLoading}>
          <Space direction="vertical" style={{ width: '100%' }} size="large">
            <Alert
              message="Exporte dados da Bling em formato CSV"
              type="info"
              showIcon
            />

            <Space>
              <Button
                type="primary"
                icon={<DownloadOutlined />}
                onClick={() => {
                  setProcessando(true)
                  csvService.exportar('estoque')
                    .then(() => {
                      message.success('Dados exportados com sucesso')
                      refetchExports()
                    })
                    .catch(() => message.error('Erro ao exportar'))
                    .finally(() => setProcessando(false))
                }}
                loading={processando}
              >
                Exportar Estoque
              </Button>
              <Button
                type="primary"
                icon={<DownloadOutlined />}
                onClick={() => {
                  setProcessando(true)
                  csvService.exportar('produtos')
                    .then(() => {
                      message.success('Dados exportados com sucesso')
                      refetchExports()
                    })
                    .catch(() => message.error('Erro ao exportar'))
                    .finally(() => setProcessando(false))
                }}
                loading={processando}
              >
                Exportar Produtos
              </Button>
            </Space>

            <div>
              <h3>Arquivos Exportados</h3>
              <Spin spinning={exportsLoading}>
                <Table
                  columns={exportColumns}
                  dataSource={exports_?.arquivos || []}
                  rowKey="nome"
                  pagination={false}
                />
              </Spin>
            </div>
          </Space>
        </Card>
      ),
    },
    {
      key: 'templates',
      label: 'Templates',
      children: (
        <Card>
          <Space direction="vertical" style={{ width: '100%' }}>
            <Alert
              message="Baixe templates CSV para cada tipo de operação"
              type="info"
              showIcon
            />
            <Space wrap>
              <Button onClick={() => csvService.gerarTemplate('adicionar')}>
                Template: Adicionar
              </Button>
              <Button onClick={() => csvService.gerarTemplate('editar')}>
                Template: Editar
              </Button>
              <Button onClick={() => csvService.gerarTemplate('deletar')}>
                Template: Deletar
              </Button>
              <Button onClick={() => csvService.gerarTemplate('atualizar_estoque')}>
                Template: Atualizar Estoque
              </Button>
              <Button onClick={() => csvService.gerarTemplate('atualizar_sku')}>
                Template: Atualizar SKU
              </Button>
            </Space>
          </Space>
        </Card>
      ),
    },
  ]

  return (
    <div>
      <h1>Importar / Exportar</h1>
      <Tabs items={tabsItems} />
    </div>
  )
}
