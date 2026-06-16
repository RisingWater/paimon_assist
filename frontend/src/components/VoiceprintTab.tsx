import { useEffect, useState } from "react"
import { Button, Space, Typography, Card, Tag, App, Spin, Empty, Select } from "antd"
import { AudioOutlined, SearchOutlined } from "@ant-design/icons"
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
              style={{ marginBottom: 12 }}
              title={
                <Typography.Text strong>
                  {u.name || `用户#${u.id}`}
                  <Typography.Text type="secondary" style={{ fontSize: 11, marginLeft: 8 }}>#{u.id}</Typography.Text>
                </Typography.Text>
              }
            >
              <Space wrap>
                {(vpsCache[u.id] || []).map((vp) => (
                  <Tag key={vp.id} closable onClose={() => handleDeleteVp(vp.id)} style={{ display: "inline-flex", alignItems: "center", gap: 6, paddingRight: 4 }}>
                    <span>#{vp.id}</span>
                    {vp.audio_path && (
                      <audio controls src={`/api/voiceprints/${vp.id}/audio`} style={{ height: 20, width: 110 }} />
                    )}
                    <Select
                      size="small"
                      style={{ width: 100, fontSize: 11 }}
                      placeholder="移动..."
                      value={undefined}
                      onChange={(targetId: number) => handleMoveVp(vp.id, targetId)}
                      options={users.filter(x => x.id !== u.id).map(x => ({
                        value: x.id,
                        label: x.name || `用户#${x.id}`,
                      }))}
                    />
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
