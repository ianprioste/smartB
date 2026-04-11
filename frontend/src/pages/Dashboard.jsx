import { Card, Row, Col, Statistic, Button, Space, Spin, Alert } from 'antd'
import { ShoppingCartOutlined, FileTextOutlined, BarsOutlined, CheckCircleOutlined } from '@ant-design/icons'
import { useQuery } from 'react-query'
import { produtoService, csvService } from '../services/api'

export default function Dashboard() {
  const { data: produtos, isLoading: produtosLoading } = useQuery('produtos', () => produtoService.listar())
  const { data: uploads, isLoading: uploadsLoading } = useQuery('uploads', () => csvService.listarUploads())
  const { data: exports_, isLoading: exportsLoading } = useQuery('exports', () => csvService.listarExports())

  const totalProdutos = produtos?.data?.length || 0
  const totalUploads = uploads?.data?.total || 0
  const totalExports = exports_?.data?.total || 0

  return (
    <div style={{ width: '100%' }}>
      <h1>Dashboard</h1>

      <Row gutter={24} style={{ marginBottom: 24 }}>
        <Col xs={24} sm={12} lg={6}>
          <Card loading={produtosLoading}>
            <Statistic
              title="Total de Produtos"
              value={totalProdutos}
              prefix={<ShoppingCartOutlined />}
            />
          </Card>
        </Col>
        <Col xs={24} sm={12} lg={6}>
          <Card loading={uploadsLoading}>
            <Statistic
              title="Arquivos Importados"
              value={totalUploads}
              prefix={<FileTextOutlined />}
            />
          </Card>
        </Col>
        <Col xs={24} sm={12} lg={6}>
          <Card loading={exportsLoading}>
            <Statistic
              title="Arquivos Exportados"
              value={totalExports}
              prefix={<FileTextOutlined />}
            />
          </Card>
        </Col>
        <Col xs={24} sm={12} lg={6}>
          <Card>
            <Statistic
              title="Status"
              value="Online"
              prefix={<CheckCircleOutlined style={{ color: '#52c41a' }} />}
            />
          </Card>
        </Col>
      </Row>

      <Row gutter={24}>
        <Col xs={24} lg={12}>
          <Card title="Ações Rápidas">
            <Space direction="vertical" style={{ width: '100%' }}>
              <Button type="primary" block>Adicionar Novo Produto</Button>
              <Button block>Importar CSV</Button>
              <Button block>Exportar Dados</Button>
              <Button block>Atualizar Estoque</Button>
            </Space>
          </Card>
        </Col>
        <Col xs={24} lg={12}>
          <Card title="Informações">
            <Alert
              message="SmartBling v1.0.0"
              description="Sistema de gerenciamento de produtos Bling com suporte a operações em massa via CSV"
              type="info"
              showIcon
              style={{ marginBottom: 16 }}
            />
            <Alert
              message="API Bling"
              description="Conectado com sucesso"
              type="success"
              showIcon
            />
          </Card>
        </Col>
      </Row>
    </div>
  )
}
