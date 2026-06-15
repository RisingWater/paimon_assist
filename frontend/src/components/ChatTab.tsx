import { useEffect, useState } from "react"
import { Button, Space, Typography, Card, Select, Input, App, Popconfirm, Tag, Empty } from "antd"
import { DeleteOutlined, EditOutlined, ClearOutlined } from "@ant-design/icons"
import { api, type HistoryMessage, type User } from "../api"

interface Props {
  users: User[]
}

export default function ChatTab({ users }: Props) {
  const { message } = App.useApp()
  const [userId, setUserId] = useState<number | undefined>()
  const [msgs, setMsgs] = useState<HistoryMessage[]>([])
  const [editingId, setEditingId] = useState<number | null>(null)
  const [editContent, setEditContent] = useState("")

  useEffect(() => {
    if (userId) {
      api.getHistory(userId).then((data) => {
        setMsgs(data.filter((m) => m.role !== "system"))
      }).catch(() => {
        message.error("加载失败")
      })
    } else {
      setMsgs([])
    }
  }, [userId])

  async function saveEdit(id: number) {
    if (!editContent.trim()) return
    await api.updateMessage(id, editContent.trim())
    setMsgs((prev) => prev.map((m) => (m.id === id ? { ...m, content: editContent.trim() } : m)))
    setEditingId(null)
    message.success("已保存")
  }

  async function handleDelete(id: number) {
    await api.deleteMessage(id)
    setMsgs((prev) => prev.filter((m) => m.id !== id))
    message.success("已删除")
  }

  async function handleClearAll() {
    if (!userId) return
    await api.clearHistory(userId)
    setMsgs([])
    message.success("历史已清空")
  }

  const roleColor: Record<string, string> = { user: "blue", assistant: "green", tool: "orange" }
  const roleLabel: Record<string, string> = { user: "用户", assistant: "派萌", tool: "工具" }

  function fmtTool(content: string, role: string): string {
    if (role !== "tool" && role !== "assistant") return content
    try {
      const parsed = JSON.parse(content)
      if (parsed.role === "tool") return `🔧 ${parsed.content}`
      if (parsed.tool_calls) {
        return parsed.tool_calls.map((tc: { function: { name: string; arguments: string } }) =>
          `🔧 ${tc.function.name}(${tc.function.arguments})`
        ).join("\n")
      }
      return content
    } catch {
      return content
    }
  }
  const selectedName = userId ? users.find((u) => u.id === userId)?.name || `用户#${userId}` : ""

  return (
    <div>
      <div style={{ display: "flex", alignItems: "center", gap: 12, marginBottom: 16 }}>
        <Typography.Text type="secondary">选择用户：</Typography.Text>
        <Select
          style={{ width: 200 }}
          placeholder="选择用户..."
          value={userId}
          onChange={setUserId}
          allowClear
          options={users.map((u) => ({
            value: u.id,
            label: u.name || `用户#${u.id}`,
          }))}
        />
        {userId && msgs.length > 0 && (
          <Popconfirm title="确定清空全部聊天记录？" onConfirm={handleClearAll}>
            <Button danger size="small" icon={<ClearOutlined />}>清空全部</Button>
          </Popconfirm>
        )}
        {userId && (
          <Typography.Text type="secondary">
            {msgs.length} 条记录
            {selectedName ? ` — ${selectedName}` : ""}
          </Typography.Text>
        )}
      </div>

      {!userId ? (
        <Empty description="请选择一个用户查看聊天记录" style={{ padding: "60px 0" }} />
      ) : msgs.length === 0 ? (
        <Empty description="还没有聊天记录" style={{ padding: "60px 0" }} />
      ) : (
        <div style={{ maxHeight: "70vh", overflow: "auto" }}>
          {msgs.map((m) => (
            <Card
              key={m.id}
              size="small"
              style={{
                marginBottom: 8,
                background: m.role === "user" ? "#e6f7ff" : "#f6ffed",
                borderLeft: `3px solid ${m.role === "user" ? "#1677ff" : "#52c41a"}`,
              }}
              title={
                <Space>
                  <Tag color={roleColor[m.role]}>{roleLabel[m.role] || m.role}</Tag>
                  <span style={{ flex: 1 }} />
                  <Button size="small" type="text" icon={<EditOutlined />} onClick={() => {
                    setEditingId(m.id)
                    setEditContent(m.content)
                  }} />
                  <Popconfirm title="删除这条消息？" onConfirm={() => handleDelete(m.id)}>
                    <Button size="small" type="text" danger icon={<DeleteOutlined />} />
                  </Popconfirm>
                </Space>
              }
            >
              {editingId === m.id ? (
                <Input.TextArea
                  autoFocus
                  value={editContent}
                  onChange={(e) => setEditContent(e.target.value)}
                  onPressEnter={(e) => {
                    if (!e.shiftKey) {
                      e.preventDefault()
                      saveEdit(m.id)
                    }
                  }}
                  onBlur={() => {
                    if (editContent.trim() && editContent.trim() !== m.content) {
                      saveEdit(m.id)
                    } else {
                      setEditingId(null)
                    }
                  }}
                  autoSize
                />
              ) : (
                <Typography.Text style={{ whiteSpace: "pre-wrap", fontSize: 14 }}>
                  {fmtTool(m.content, m.role)}
                </Typography.Text>
              )}
            </Card>
          ))}
        </div>
      )}
    </div>
  )
}
