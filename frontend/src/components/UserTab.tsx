import { useState } from "react"
import { Button, Space, Typography, Card, Input, App, Popconfirm, Spin, Empty } from "antd"
import { PlusOutlined } from "@ant-design/icons"
import { api, type User } from "../api"
import CreateUserDialog from "../dialogs/CreateUserDialog"

const PAGE_SIZE = 20

interface Props {
  users: User[]
  loading: boolean
  onRefresh: () => void
}

export default function UserTab({ users, loading, onRefresh }: Props) {
  const { message } = App.useApp()
  const [page, setPage] = useState(1)
  const [editingUid, setEditingUid] = useState<number | null>(null)
  const [editName, setEditName] = useState("")
  const [dlgCreate, setDlgCreate] = useState(false)

  const totalPages = Math.max(1, Math.ceil(users.length / PAGE_SIZE))
  const pageUsers = users.slice((page - 1) * PAGE_SIZE, page * PAGE_SIZE)

  async function handleRename(uid: number, name: string) {
    await api.renameUser(uid, name)
    message.success(`已命名: ${name}`)
    onRefresh()
  }

  async function handleDelete(uid: number) {
    await api.deleteUser(uid)
    message.success("已删除用户")
    onRefresh()
  }

  return (
    <div>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 16 }}>
        <Typography.Text type="secondary">
          {loading ? "加载中..." : `${users.length} 个用户 (第 ${page}/${totalPages} 页)`}
        </Typography.Text>
        <Button type="primary" icon={<PlusOutlined />} onClick={() => setDlgCreate(true)}>
          新建用户
        </Button>
      </div>

      <Spin spinning={loading}>
        {!loading && users.length === 0 ? (
          <Empty description="还没有用户" style={{ padding: "60px 0" }}>
            <Button type="primary" onClick={() => setDlgCreate(true)}>新建用户</Button>
          </Empty>
        ) : (
          pageUsers.map((u) => (
            <Card
              key={u.id}
              size="small"
              style={{ marginBottom: 12 }}
              title={
                <Space>
                  {editingUid === u.id ? (
                    <Input
                      size="small"
                      value={editName}
                      onChange={(e) => setEditName(e.target.value)}
                      onPressEnter={() => {
                        const v = editName.trim()
                        if (v) handleRename(u.id, v)
                        setEditingUid(null)
                      }}
                      onBlur={() => setEditingUid(null)}
                      style={{ width: 140 }}
                      autoFocus
                    />
                  ) : (
                    <Typography.Text
                      onClick={() => { setEditingUid(u.id); setEditName(u.name || "") }}
                      style={{ cursor: "pointer", ...(!u.name ? { color: "#888", fontStyle: "italic" } : {}) }}
                    >
                      {u.name || `用户#${u.id}`}
                    </Typography.Text>
                  )}
                  <Typography.Text type="secondary" style={{ fontSize: 11 }}>#{u.id}</Typography.Text>
                </Space>
              }
              extra={
                u.name === "定时任务" ? null : (
                  <Popconfirm title="确定删除该用户及其所有声纹？" onConfirm={() => handleDelete(u.id)}>
                    <Button size="small" danger>删除</Button>
                  </Popconfirm>
                )
              }
            >
              <Typography.Text type="secondary" style={{ fontSize: 12 }}>
                创建于 {u.created_at}
              </Typography.Text>
            </Card>
          ))
        )}
      </Spin>

      {totalPages > 1 && (
        <div style={{ display: "flex", justifyContent: "center", marginTop: 16 }}>
          <Space>
            <Button size="small" disabled={page <= 1} onClick={() => setPage(page - 1)}>上一页</Button>
            {Array.from({ length: totalPages }, (_, i) => i + 1).map((p) => (
              <Button key={p} size="small" type={p === page ? "primary" : "default"} onClick={() => setPage(p)}>
                {p}
              </Button>
            ))}
            <Button size="small" disabled={page >= totalPages} onClick={() => setPage(page + 1)}>下一页</Button>
          </Space>
        </div>
      )}

      <CreateUserDialog open={dlgCreate} onClose={() => setDlgCreate(false)} onCreated={onRefresh} />
    </div>
  )
}
