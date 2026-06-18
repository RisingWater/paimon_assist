import { useEffect, useState } from "react"
import { Button, Select, Input, Typography, App, Spin } from "antd"
import { SaveOutlined } from "@ant-design/icons"
import { type User } from "../api"

interface Props {
  users: User[]
}

export default function MemoryTab({ users }: Props) {
  const { message } = App.useApp()
  const [target, setTarget] = useState("long")
  const [content, setContent] = useState("")
  const [summary, setSummary] = useState("")
  const [loading, setLoading] = useState(false)

  async function load() {
    setLoading(true)
    try {
      const res = await fetch(`/api/memory/${target}`)
      const data = await res.json()
      const raw = data.content || ""
      setContent(raw)
      // 提取摘要行预览
      const m = raw.match(/^> 摘要[：:](.+)/m)
      setSummary(m ? m[1] : "（暂无摘要）")
    } catch { message.error("加载失败") }
    finally { setLoading(false) }
  }

  useEffect(() => { load() }, [target])

  async function handleSave() {
    try {
      const res = await fetch(`/api/memory/${target}`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ content }),
      })
      if (res.ok) {
        message.success("已保存，摘要已自动更新")
        load()
      } else {
        message.error("保存失败")
      }
    } catch { message.error("保存失败") }
  }

  const options = [
    { value: "long", label: "长期记忆 (memory.md)" },
    ...users.map((u) => ({
      value: String(u.id),
      label: `${u.name || "用户#" + u.id} — 中期记忆`,
    })),
  ]

  return (
    <div>
      <div style={{ display: "flex", alignItems: "center", gap: 12, marginBottom: 16 }}>
        <Typography.Text type="secondary">编辑记忆：</Typography.Text>
        <Select value={target} onChange={setTarget} style={{ width: 280 }} options={options} />
        <Button type="primary" icon={<SaveOutlined />} onClick={handleSave}>保存</Button>
      </div>
      <Typography.Paragraph type="secondary" style={{ marginBottom: 8, background: "#f6ffed", padding: "8px 12px", borderRadius: 6 }}>
        当前摘要：{summary}
      </Typography.Paragraph>
      <Spin spinning={loading}>
        <Input.TextArea
          value={content}
          onChange={(e) => setContent(e.target.value)}
          placeholder="格式：- 事实描述"
          autoSize={false}
          style={{ minHeight: "60vh", fontFamily: "monospace", fontSize: 14 }}
        />
      </Spin>
    </div>
  )
}
