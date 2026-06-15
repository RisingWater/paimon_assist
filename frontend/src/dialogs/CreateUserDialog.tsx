import { useState } from "react"
import { Modal, Input, App } from "antd"
import { api } from "../api"

export default function CreateUserDialog({
  open,
  onClose,
  onCreated,
}: {
  open: boolean
  onClose: () => void
  onCreated: () => void
}) {
  const { message } = App.useApp()
  const [name, setName] = useState("")

  async function create() {
    try {
      await api.createUser(name.trim())
      message.success("用户已创建")
      setName("")
      onClose()
      onCreated()
    } catch {
      message.error("创建失败")
    }
  }

  return (
    <Modal
      title="新建用户"
      open={open}
      onCancel={onClose}
      onOk={create}
      okText="创建"
      cancelText="取消"
    >
      <Input
        autoFocus
        value={name}
        onChange={(e) => setName(e.target.value)}
        onPressEnter={create}
        placeholder="用户名字（可选）"
      />
    </Modal>
  )
}
