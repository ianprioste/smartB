import { Table, Button, Space, Modal, Form, Input, InputNumber, Card, message, Spin, Tabs, Empty, Tooltip } from 'antd'
import { PlusOutlined, EditOutlined, DeleteOutlined, ReloadOutlined, BgColorsOutlined } from '@ant-design/icons'
import { useQuery } from 'react-query'
import { useState } from 'react'
import { produtoService } from '../services/api'

export default function Produtos() {
  const { data: response, isLoading, refetch } = useQuery('produtos', () => produtoService.listar())
  const [isModalOpen, setIsModalOpen] = useState(false)
  const [form] = Form.useForm()
  const [editingId, setEditingId] = useState(null)

  const produtos = response?.data?.data || []

  const columns = [
    {
      title: 'SKU',
      dataIndex: ['data', 'numero'],
      key: 'sku',
      width: 120,
    },
    {
      title: 'Nome',
      dataIndex: ['data', 'descricao'],
      key: 'nome',
      ellipsis: true,
    },
    {
      title: 'Preço',
      dataIndex: ['data', 'preco'],
      key: 'preco',
      width: 120,
      render: (text) => `R$ ${parseFloat(text || 0).toFixed(2)}`,
    },
    {
      title: 'Estoque',
      dataIndex: ['data', 'estoque'],
      key: 'estoque',
      width: 100,
      render: (text) => text || 0,
    },
    {
      title: 'Ações',
      key: 'acoes',
      width: 150,
      render: (_, record) => (
        <Space size="small">
          <Tooltip title="Editar">
            <Button
              type="primary"
              size="small"
              icon={<EditOutlined />}
              onClick={() => {
                setEditingId(record.data.id)
                form.setFieldsValue(record.data)
                setIsModalOpen(true)
              }}
            />
          </Tooltip>
          <Tooltip title="Deletar">
            <Button
              type="primary"
              danger
              size="small"
              icon={<DeleteOutlined />}
              onClick={() => {
                Modal.confirm({
                  title: 'Confirmar Exclusão',
                  content: `Deseja deletar o produto ${record.data.numero}?`,
                  okText: 'Sim',
                  cancelText: 'Não',
                  onOk: async () => {
                    try {
                      await produtoService.deletar(record.data.id)
                      message.success('Produto deletado com sucesso')
                      refetch()
                    } catch (error) {
                      message.error('Erro ao deletar produto')
                    }
                  },
                })
              }}
            />
          </Tooltip>
        </Space>
      ),
    },
  ]

  const handleAddProduct = () => {
    setEditingId(null)
    form.resetFields()
    setIsModalOpen(true)
  }

  const handleSave = async (values) => {
    try {
      if (editingId) {
        await produtoService.atualizar(editingId, values)
        message.success('Produto atualizado com sucesso')
      } else {
        await produtoService.criar(values)
        message.success('Produto criado com sucesso')
      }
      setIsModalOpen(false)
      refetch()
    } catch (error) {
      message.error('Erro ao salvar produto')
    }
  }

  return (
    <div>
      <Card
        title="Gerenciador de Produtos"
        extra={
          <Space>
            <Button
              type="primary"
              icon={<PlusOutlined />}
              onClick={handleAddProduct}
            >
              Novo Produto
            </Button>
            <Button icon={<ReloadOutlined />} onClick={() => refetch()} />
          </Space>
        }
      >
        <Spin spinning={isLoading}>
          {produtos.length > 0 ? (
            <Table
              columns={columns}
              dataSource={produtos}
              rowKey={(record) => record.data?.id}
              pagination={{ pageSize: 10 }}
              scroll={{ x: 800 }}
            />
          ) : (
            <Empty description="Nenhum produto encontrado" />
          )}
        </Spin>
      </Card>

      <Modal
        title={editingId ? 'Editar Produto' : 'Novo Produto'}
        open={isModalOpen}
        onOk={() => form.submit()}
        onCancel={() => setIsModalOpen(false)}
      >
        <Form
          form={form}
          layout="vertical"
          onFinish={handleSave}
        >
          <Form.Item
            name="numero"
            label="SKU"
            rules={[{ required: true, message: 'SKU é obrigatório' }]}
          >
            <Input />
          </Form.Item>
          <Form.Item
            name="descricao"
            label="Nome"
            rules={[{ required: true, message: 'Nome é obrigatório' }]}
          >
            <Input />
          </Form.Item>
          <Form.Item
            name="descricaoComplementar"
            label="Descrição"
          >
            <Input.TextArea rows={3} />
          </Form.Item>
          <Form.Item
            name="preco"
            label="Preço"
            rules={[{ required: true, message: 'Preço é obrigatório' }]}
          >
            <InputNumber min={0} step={0.01} />
          </Form.Item>
          <Form.Item
            name="estoque"
            label="Estoque"
          >
            <InputNumber min={0} />
          </Form.Item>
        </Form>
      </Modal>
    </div>
  )
}
