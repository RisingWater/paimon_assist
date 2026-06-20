import { useEffect, useState } from "react"
import { Button, Switch, Typography, App, Spin, Tag } from "antd"
import { SaveOutlined } from "@ant-design/icons"

interface ToolInfo {
  name: string
  description: string
  silent_default: boolean
}

export default function ToolConfigTab() {
  const { message } = App.useApp()
  const [tools, setTools] = useState<ToolInfo[]>([])
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

  function effectiveSilent(name: string, silentDefault: boolean) {
    return silentDefault || silent.has(name)
  }

  async function handleSave() {
    const overrides = tools.filter(t => {
      const eff = effectiveSilent(t.name, t.silent_default)
      return eff !== t.silent_default  // 只保存与默认不同的
    }).map(t => t.name)
    try {
      const res = await fetch("/api/tool-config", {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ silent: overrides }),
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
          开关对应工具调用时是否播放 TTS 提示语。
          <Tag style={{ marginLeft: 8 }}>默认</Tag> = 工具自身声明，无需手动保存。
        </Typography.Text>
        <Button type="primary" icon={<SaveOutlined />} onClick={handleSave}>保存</Button>
      </div>
      <Spin spinning={loading}>
        {tools.map((t) => (
          <div key={t.name} style={{ display: "flex", alignItems: "center", gap: 12, padding: "8px 0", borderBottom: "1px solid #f0f0f0" }}>
            <Switch
              size="small"
              checked={effectiveSilent(t.name, t.silent_default)}
              onChange={(v) => toggle(t.name, v)}
            />
            <Typography.Text code style={{ width: 160 }}>{t.name}</Typography.Text>
            {t.silent_default && <Tag color="blue" style={{ fontSize: 11, lineHeight: "18px" }}>默认</Tag>}
            <Typography.Text type="secondary" style={{ fontSize: 13 }}>{t.description}</Typography.Text>
          </div>
        ))}
      </Spin>
    </div>
  )
}
