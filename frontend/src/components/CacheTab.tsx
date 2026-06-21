import { useEffect, useState } from "react"
import { Button, Input, Table, Typography, App, Popconfirm, Tag, Space } from "antd"
import { DeleteOutlined, ClearOutlined, SoundOutlined } from "@ant-design/icons"

interface CacheItem {
  id: number
  text: string
  backend: string
  created_at: string
  audio_path: string
}

export default function CacheTab() {
  const { message } = App.useApp()
  const [items, setItems] = useState<CacheItem[]>([])
  const [loading, setLoading] = useState(false)
  const [search, setSearch] = useState("")
  const [testText, setTestText] = useState("")
  const [speaking, setSpeaking] = useState(false)

  async function load(q?: string) {
    setLoading(true)
    try {
      const res = await fetch(`/api/tts-cache?search=${encodeURIComponent(q || search)}`)
      setItems(await res.json())
    } catch { message.error("加载失败") }
    finally { setLoading(false) }
  }

  useEffect(() => { load() }, [])

  async function handleDelete(id: number) {
    await fetch(`/api/tts-cache/${id}`, { method: "DELETE" })
    message.success("已删除")
    load()
  }

  async function handleClear() {
    await fetch("/api/tts-cache", { method: "DELETE" })
    message.success("已清空")
    load()
  }

  async function handleTestSpeak() {
    if (!testText.trim()) return
    setSpeaking(true)
    try {
      await fetch("/api/tts/speak", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ text: testText.trim(), play: true }),
      })
      message.success("已播放")
      load()
    } catch { message.error("播放失败") }
    finally { setSpeaking(false); setTestText("") }
  }

  const backendColor: Record<string, string> = { vits: "blue", http: "orange" }

  return (
    <div>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 16 }}>
        <Typography.Text type="secondary">{items.length} 条缓存</Typography.Text>
        <Space>
          <Input.Search
            placeholder="搜索文本..."
            value={search}
            onChange={e => setSearch(e.target.value)}
            onSearch={() => load(search)}
            style={{ width: 240 }}
            allowClear
          />
          <Popconfirm title="确定清空全部缓存？" onConfirm={handleClear}>
            <Button danger icon={<ClearOutlined />}>清空全部</Button>
          </Popconfirm>
        </Space>
      </div>

      <div style={{ display: "flex", gap: 8, marginBottom: 16 }}>
        <Input.TextArea
          value={testText}
          onChange={e => setTestText(e.target.value)}
          onPressEnter={e => { if (!e.shiftKey) { e.preventDefault(); handleTestSpeak() } }}
          placeholder="输入文字测试说话…"
          autoSize={{ minRows: 1, maxRows: 2 }}
          style={{ flex: 1 }}
        />
        <Button type="primary" icon={<SoundOutlined />} onClick={handleTestSpeak} loading={speaking}>
          说话
        </Button>
      </div>

      <Table
        dataSource={items}
        rowKey="id"
        size="small"
        loading={loading}
        scroll={{ x: "max-content" }}
        pagination={{ pageSize: 20 }}
        columns={[
          { title: "文本", dataIndex: "text", ellipsis: true },
          {
            title: "类型", dataIndex: "backend", width: 80,
            render: (v: string) => <Tag color={backendColor[v]}>{v}</Tag>,
          },
          { title: "时间", dataIndex: "created_at", width: 160 },
          {
            title: "试听", key: "play", width: 150,
            render: (_: unknown, r: CacheItem) => (
              <audio controls src={`/__cache_audio/${r.id}`} style={{ height: 24, width: 140 }} />
            ),
          },
          {
            title: "操作", key: "actions", width: 60,
            render: (_: unknown, r: CacheItem) => (
              <Popconfirm title="删除？" onConfirm={() => handleDelete(r.id)}>
                <Button size="small" danger icon={<DeleteOutlined />} />
              </Popconfirm>
            ),
          },
        ]}
      />
    </div>
  )
}
