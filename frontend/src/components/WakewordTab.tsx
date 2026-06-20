import { useEffect, useState } from "react"
import { Table, Typography, App, Popconfirm, Button, Space, Tag } from "antd"
import { DeleteOutlined, SwapOutlined, ReloadOutlined } from "@ant-design/icons"
import { api, type WakewordFile } from "../api"

function fmtTime(ts: number) {
  return new Date(ts * 1000).toLocaleString("zh-CN")
}

function fmtSize(bytes: number) {
  if (bytes < 1024) return bytes + " B"
  return (bytes / 1024).toFixed(1) + " KB"
}

export default function WakewordTab() {
  const { message } = App.useApp()
  const [positive, setPositive] = useState<WakewordFile[]>([])
  const [negative, setNegative] = useState<WakewordFile[]>([])
  const [loading, setLoading] = useState(false)

  async function load() {
    setLoading(true)
    try {
      const [pos, neg] = await Promise.all([
        api.listWakewordFiles("positive"),
        api.listWakewordFiles("negative"),
      ])
      setPositive(pos)
      setNegative(neg)
    } catch { message.error("加载失败") }
    finally { setLoading(false) }
  }

  useEffect(() => { load() }, [])

  async function handleMove(filename: string, from: string, to: string) {
    try {
      await api.moveWakeword(filename, from, to)
      message.success("已移动")
      load()
    } catch { message.error("移动失败") }
  }

  async function handleDelete(category: string, filename: string) {
    try {
      await api.deleteWakeword(category, filename)
      message.success("已删除")
      load()
    } catch { message.error("删除失败") }
  }

  const columns = (category: string) => [
    {
      title: "文件名", dataIndex: "filename", ellipsis: true,
      render: (v: string) => <Typography.Text code style={{ fontSize: 12 }}>{v}</Typography.Text>,
    },
    { title: "大小", dataIndex: "size", width: 80, render: (v: number) => fmtSize(v) },
    { title: "时间", dataIndex: "mtime", width: 160, render: (v: number) => fmtTime(v) },
    {
      title: "播放", key: "play", width: 200,
      render: (_: unknown, r: WakewordFile) => (
        <audio controls src={api.wakewordAudioUrl(category, r.filename)} style={{ height: 24, width: 190 }} />
      ),
    },
    {
      title: "操作", key: "actions", width: 180,
      render: (_: unknown, r: WakewordFile) => {
        const target = category === "positive" ? "negative" : "positive"
        const label = target === "positive" ? "→ 正例" : "→ 负例"
        return (
          <Space>
            <Popconfirm title={`移动到「${target === "positive" ? "正确唤醒" : "误唤醒"}」？`}
              onConfirm={() => handleMove(r.filename, category, target)}>
              <Button size="small" icon={<SwapOutlined />}>{label}</Button>
            </Popconfirm>
            <Popconfirm title="确定删除？" onConfirm={() => handleDelete(category, r.filename)}>
              <Button size="small" danger icon={<DeleteOutlined />} />
            </Popconfirm>
          </Space>
        )
      },
    },
  ]

  return (
    <div>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 16 }}>
        <Typography.Text type="secondary">
          正例 {positive.length} 条 / 负例 {negative.length} 条
        </Typography.Text>
        <Button icon={<ReloadOutlined />} onClick={load} loading={loading} size="small">刷新</Button>
      </div>

      <Typography.Title level={5}>
        <Tag color="green">正例 Positive</Tag> 正确唤醒（LLM 正常回复）
      </Typography.Title>
      <Table dataSource={positive} rowKey="filename" size="small" loading={loading}
        pagination={false} columns={columns("positive")}
        locale={{ emptyText: "暂无" }} style={{ marginBottom: 24 }} />

      <Typography.Title level={5}>
        <Tag color="red">负例 Negative</Tag> 误唤醒（__SKIP__ / 无有效语音）
      </Typography.Title>
      <Table dataSource={negative} rowKey="filename" size="small" loading={loading}
        pagination={false} columns={columns("negative")}
        locale={{ emptyText: "暂无" }} />
    </div>
  )
}
