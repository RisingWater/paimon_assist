import { useEffect, useState } from "react"
import { Button, Space, Typography, Card, Tag, App, Spin, Empty } from "antd"
import { AudioOutlined, SearchOutlined, HolderOutlined } from "@ant-design/icons"
import { api, type User, type Voiceprint } from "../api"
import AddVoiceprintDialog from "../dialogs/AddVoiceprintDialog"
import DetectDialog from "../dialogs/DetectDialog"

interface Props {
  users: User[]
  loading: boolean
  onRefresh: () => void
}

export default function VoiceprintTab({ users, loading, onRefresh }: Props) {
  const { message } = App.useApp()
  const [vpsCache, setVpsCache] = useState<Record<number, Voiceprint[]>>({})
  const [dlgAddVp, setDlgAddVp] = useState(false)
  const [dlgDetect, setDlgDetect] = useState(false)
  const [dragOver, setDragOver] = useState<number | null>(null)

  useEffect(() => {
    async function load() {
      const cache: Record<number, Voiceprint[]> = {}
      await Promise.all(
        users.map(async (u) => {
          try { cache[u.id] = await api.listVoiceprints(u.id) } catch { cache[u.id] = [] }
        })
      )
      setVpsCache(cache)
    }
    load()
  }, [users])

  async function handleDeleteVp(vpId: number) {
    await api.deleteVoiceprint(vpId)
    message.success("已删除声纹")
    onRefresh()
  }

  async function handleMoveVp(vpId: number, targetUserId: number) {
    await api.moveVoiceprint(vpId, targetUserId)
    message.success("已移动声纹")
    onRefresh()
  }

  function onDragStart(e: React.DragEvent, vpId: number, fromUserId: number) {
    e.dataTransfer.setData("vpId", String(vpId))
    e.dataTransfer.setData("fromUserId", String(fromUserId))
    e.dataTransfer.effectAllowed = "move"
  }

  function onDragOver(e: React.DragEvent, userId: number) {
    e.preventDefault()
    e.dataTransfer.dropEffect = "move"
    setDragOver(userId)
  }

  function onDragLeave() {
    setDragOver(null)
  }

  function onDrop(e: React.DragEvent, toUserId: number) {
    e.preventDefault()
    setDragOver(null)
    const vpId = Number(e.dataTransfer.getData("vpId"))
    const fromUserId = Number(e.dataTransfer.getData("fromUserId"))
    if (vpId && fromUserId !== toUserId) {
      handleMoveVp(vpId, toUserId)
    }
  }

  const usersWithVps = users.filter((u) => (vpsCache[u.id] || []).length > 0)

  return (
    <div>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 16 }}>
        <Typography.Text type="secondary">
          共 {usersWithVps.length} 个用户有声纹
        </Typography.Text>
        <Space>
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
        </Space>
      </div>

      <Spin spinning={loading}>
        {!loading && usersWithVps.length === 0 ? (
          <Empty description="还没有声纹" style={{ padding: "60px 0" }}>
            <Button onClick={() => {
              if (users.length === 0) { message.warning("请先创建用户"); return }
              setDlgAddVp(true)
            }}>添加声纹</Button>
          </Empty>
        ) : (
          usersWithVps.map((u) => (
            <Card
              key={u.id}
              size="small"
              style={{
                marginBottom: 12,
                border: dragOver === u.id ? "2px dashed #1677ff" : undefined,
                background: dragOver === u.id ? "#e6f4ff" : undefined,
                transition: "background 0.2s, border 0.2s",
              }}
              onDragOver={(e) => onDragOver(e, u.id)}
              onDragLeave={onDragLeave}
              onDrop={(e) => onDrop(e, u.id)}
              title={
                <Typography.Text strong>
                  {u.name || `用户#${u.id}`}
                  <Typography.Text type="secondary" style={{ fontSize: 11, marginLeft: 8 }}>#{u.id}</Typography.Text>
                </Typography.Text>
              }
            >
              <Space wrap>
                {(vpsCache[u.id] || []).map((vp) => (
                  <Tag
                    key={vp.id}
                    closable
                    draggable
                    onDragStart={(e) => onDragStart(e, vp.id, u.id)}
                    onClose={() => handleDeleteVp(vp.id)}
                    style={{ display: "inline-flex", alignItems: "center", gap: 6, cursor: "grab" }}
                  >
                    <HolderOutlined style={{ color: "#999", cursor: "grab" }} />
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

      <AddVoiceprintDialog open={dlgAddVp} users={users} onClose={() => setDlgAddVp(false)} onAdded={onRefresh} />
      <DetectDialog open={dlgDetect} onClose={() => setDlgDetect(false)} />
    </div>
  )
}
