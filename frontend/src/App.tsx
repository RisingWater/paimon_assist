import { useEffect, useState } from "react"
import { Layout, Button, Space, Typography, Card, Tag, Select, Input, App, Popconfirm, Spin, Empty } from "antd"
import { PlusOutlined, AudioOutlined, ReloadOutlined, SearchOutlined } from "@ant-design/icons"
import { api, type User, type Voiceprint } from "./api"
import CreateUserDialog from "./dialogs/CreateUserDialog"
import AddVoiceprintDialog from "./dialogs/AddVoiceprintDialog"
import DetectDialog from "./dialogs/DetectDialog"

const { Header, Content } = Layout
const PAGE_SIZE = 20

export default function Root() {
  const { message } = App.useApp()
  const [users, setUsers] = useState<User[]>([])
  const [page, setPage] = useState(1)
  const [loading, setLoading] = useState(true)
  const [vpsCache, setVpsCache] = useState<Record<number, Voiceprint[]>>({})

  const [editingUid, setEditingUid] = useState<number | null>(null)
  const [editName, setEditName] = useState("")

  const [dlgCreate, setDlgCreate] = useState(false)
  const [dlgAddVp, setDlgAddVp] = useState(false)
  const [dlgDetect, setDlgDetect] = useState(false)

  async function loadData() {
    setLoading(true)
    try {
      const users = await api.listUsers()
      setUsers(users)
      const start = (page - 1) * PAGE_SIZE
      const pageUsers = users.slice(start, start + PAGE_SIZE)
      const cache: Record<number, Voiceprint[]> = {}
      await Promise.all(
        pageUsers.map(async (u) => {
          try { cache[u.id] = await api.listVoiceprints(u.id) } catch { cache[u.id] = [] }
        })
      )
      setVpsCache(cache)
    } catch {
      message.error("API 连接失败")
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => { loadData() }, [page])

  const totalPages = Math.max(1, Math.ceil(users.length / PAGE_SIZE))
  const pageUsers = users.slice((page - 1) * PAGE_SIZE, page * PAGE_SIZE)

  async function handleRename(uid: number, name: string) {
    await api.renameUser(uid, name)
    message.success(`已命名: ${name}`)
    loadData()
  }

  async function handleDeleteUser(uid: number) {
    await api.deleteUser(uid)
    message.success("已删除用户")
    loadData()
  }

  async function handleDeleteVp(vpId: number) {
    await api.deleteVoiceprint(vpId)
    message.success("已删除声纹")
    loadData()
  }

  return (
    <Layout style={{ minHeight: "100vh", background: "#f5f5f5" }}>
      <Header style={{ display: "flex", alignItems: "center", gap: 16, background: "#fff", borderBottom: "1px solid #f0f0f0", padding: "0 32px" }}>
        <Typography.Title level={4} style={{ color: "#1677ff", margin: 0, whiteSpace: "nowrap" }}>
          派萌助手
        </Typography.Title>
        <Typography.Text type="secondary">用户 & 声纹管理</Typography.Text>
        <span style={{ flex: 1 }} />
        <Space>
          <Button type="primary" icon={<PlusOutlined />} onClick={() => setDlgCreate(true)}>
            新建用户
          </Button>
          <Button
            icon={<AudioOutlined />}
            onClick={() => {
              if (users.length === 0) { message.warning("请先创建用户"); return }
              setDlgAddVp(true)
            }}
          >
            添加声纹
          </Button>
          <Button icon={<SearchOutlined />} onClick={() => setDlgDetect(true)}>
            声纹检测
          </Button>
          <Button icon={<ReloadOutlined />} onClick={loadData}>刷新</Button>
        </Space>
      </Header>
      <Content style={{ maxWidth: 960, width: "100%", margin: "24px auto", padding: "0 20px" }}>
        <div style={{ marginBottom: 16, color: "#888", fontSize: 13 }}>
          {loading ? "加载中..." : `${users.length} 个用户 (第 ${page}/${totalPages} 页)`}
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
                  <Popconfirm
                    title="确定删除该用户及其所有声纹？"
                    onConfirm={() => handleDeleteUser(u.id)}
                  >
                    <Button size="small" danger>删除用户</Button>
                  </Popconfirm>
                }
              >
                <Space wrap>
                  <Typography.Text type="secondary" style={{ fontSize: 11 }}>
                    声纹 ({(vpsCache[u.id] || []).length}):
                  </Typography.Text>
                  <Select
                    size="small"
                    placeholder="移动声纹到..."
                    style={{ width: 150 }}
                    onChange={() => {}}
                    options={users.filter((t) => t.id !== u.id).map((t) => ({
                      value: t.id,
                      label: t.name || `用户#${t.id}`,
                    }))}
                  />
                  {(vpsCache[u.id] || []).map((vp) => (
                    <Tag key={vp.id} closable onClose={() => handleDeleteVp(vp.id)} style={{ display: "inline-flex", alignItems: "center", gap: 6 }}>
                      <span>#{vp.id}</span>
                      {vp.audio_path && (
                        <audio controls src={`/api/voiceprints/${vp.id}/audio`} style={{ height: 20, width: 110 }} />
                      )}
                    </Tag>
                  ))}
                </Space>
              </Card>
            ))
          )}
        </Spin>

        <div style={{ display: "flex", justifyContent: "center", marginTop: 16 }}>
          <Space>
            <Button size="small" disabled={page <= 1} onClick={() => setPage(page - 1)}>上一页</Button>
            {Array.from({ length: totalPages }, (_, i) => i + 1).map((p) => (
              <Button
                key={p}
                size="small"
                type={p === page ? "primary" : "default"}
                onClick={() => setPage(p)}
              >
                {p}
              </Button>
            ))}
            <Button size="small" disabled={page >= totalPages} onClick={() => setPage(page + 1)}>下一页</Button>
          </Space>
        </div>
      </Content>

      <CreateUserDialog open={dlgCreate} onClose={() => setDlgCreate(false)} onCreated={loadData} />
      <AddVoiceprintDialog open={dlgAddVp} users={users} onClose={() => setDlgAddVp(false)} onAdded={loadData} />
      <DetectDialog open={dlgDetect} onClose={() => setDlgDetect(false)} />
    </Layout>
  )
}
