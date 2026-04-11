import { Card, Form, Input, Button, Space, message, Alert, Spin } from 'antd'
import { useState } from 'react'
import { useQuery } from 'react-query'
import { configService } from '../services/api'

export default function Configuracoes() {
  const [form] = Form.useForm()
  const [loading, setLoading] = useState(false)
  const { data: health, isLoading: healthLoading } = useQuery('health', () => configService.verificarSaude())
  const { data: blingStatus, refetch: refetchBling } = useQuery('bling-status', () => configService.validarBling())

  const handleConfigurarBling = async (values) => {
    setLoading(true)
    try {
      await configService.configurarBling(values.api_key)
      message.success('API Bling configurada com sucesso')
      refetchBling()
      form.resetFields()
    } catch (error) {
      message.error('Erro ao configurar API Bling')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div>
      <h1>Configurações</h1>

      <div style={{ marginBottom: 24 }}>
        <Card title="Status do Sistema" loading={healthLoading}>
          <Space direction="vertical">
            <Alert
              message={`Status: ${health?.status === 'ok' ? 'Online' : 'Offline'}`}
              type={health?.status === 'ok' ? 'success' : 'error'}
              showIcon
            />
            <Alert
              message={`Versão: ${health?.versao || 'N/A'}`}
              type="info"
              showIcon
            />
          </Space>
        </Card>
      </div>

      <div style={{ marginBottom: 24 }}>
        <Card title="Status Bling API">
          <Spin spinning={!blingStatus}>
            <Alert
              message={`Status: ${blingStatus?.conectado ? 'Conectado' : 'Desconectado'}`}
              type={blingStatus?.conectado ? 'success' : 'error'}
              showIcon
              description={blingStatus?.mensagem}
            />
          </Spin>
        </Card>
      </div>

      <div>
        <Card title="Configurar API Bling">
          <Form
            form={form}
            layout="vertical"
            onFinish={handleConfigurarBling}
          >
            <Form.Item
              name="api_key"
              label="Chave de API Bling"
              rules={[
                { required: true, message: 'Chave de API é obrigatória' },
                { min: 10, message: 'Chave de API inválida' },
              ]}
            >
              <Input.Password placeholder="Cole sua chave de API aqui" />
            </Form.Item>

            <Form.Item>
              <Button type="primary" htmlType="submit" loading={loading}>
                Salvar Configurações
              </Button>
            </Form.Item>
          </Form>
        </Card>
      </div>
    </div>
  )
}
