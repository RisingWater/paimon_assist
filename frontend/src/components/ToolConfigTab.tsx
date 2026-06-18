import { useEffect, useState } from "react"
import { Button, Switch, Typography, App, Spin } from "antd"
import { SaveOutlined } from "@ant-design/icons"

export default function ToolConfigTab() {
  const { message } = App.useApp()
  const [tools, setTools] = useState<{ name: string; description: string }[]>([])
  const [silent, setSilent] = useState<Set<string>>(new Set())
  const [loading, setLoading] = useState(false)

  async function load() {
    setLoading(true)
    try {
      const res = await fetch("/api/tool-config")
      const data = await res.json()
      setTools(data.tools)
      setSilent(new Set(data.silent))
    } catch { message.error("加载失败") }
    finally { setLoading(false) }
  }

  useEffect(() => { load() }, [])

  async function handleSave() {
    try {
      const res = await fetch("/api/tool-config", {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ silent: [...silent] }),
      })
      if (res.ok) message.success("已保存")
      else message.error("保存失败")
    } catch { message.error("保存失败") }
  }

  function toggle(name: string, checked: boolean) {
    const next = new Set(silent)
    if (checked) next.add(name)
    else next.delete(name)
    setSilent(next)
  }

  return (
    <div>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 16 }}>
        <Typography.Text type="secondary">
          开关对应工具调用时是否播放 TTS 提示语（如"让我查一下"）。打开 = 静默，不播提示语。
        </Typography.Text>
        <Button type="primary" icon={<SaveOutlined />} onClick={handleSave}>保存</Button>
      </div>
      <Spin spinning={loading}>
        {tools.map((t) => (
          <div key={t.name} style={{ display: "flex", alignItems: "center", gap: 12, padding: "8px 0", borderBottom: "1px solid #f0f0f0" }}>
            <Switch size="small" checked={silent.has(t.name)} onChange={(v) => toggle(t.name, v)} />
            <Typography.Text code style={{ width: 160 }}>{t.name}</Typography.Text>
            <Typography.Text type="secondary" style={{ fontSize: 13 }}>{t.description}</Typography.Text>
          </div>
        ))}
      </Spin>
    </div>
  )
}
