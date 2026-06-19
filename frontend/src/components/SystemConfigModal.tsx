import { useEffect, useState } from "react"
import { Modal, Tabs, Radio, Typography, Button, Switch, App, Spin } from "antd"
import { SaveOutlined } from "@ant-design/icons"

interface ToolInfo {
  name: string
  description: string
}

interface Props {
  open: boolean
  onClose: () => void
}

export default function SystemConfigModal({ open, onClose }: Props) {
  const { message } = App.useApp()
  const [ttsBackend, setTtsBackend] = useState("vits")
  const [tools, setTools] = useState<ToolInfo[]>([])
  const [silent, setSilent] = useState<Set<string>>(new Set())
  const [loading, setLoading] = useState(false)

  useEffect(() => {
    if (!open) return
    setLoading(true)

    // 加载工具配置
    fetch("/api/tool-config").then(r => r.json()).then(data => {
      setTools(data.tools)
      setSilent(new Set(data.silent))
    }).catch(() => {})

    // 加载 TTS 配置
    fetch("/api/system-config").then(r => r.json()).then(data => {
      setTtsBackend(data.tts_backend || "vits")
    }).catch(() => {}).finally(() => setLoading(false))
  }, [open])

  async function saveToolConfig() {
    try {
      await fetch("/api/tool-config", {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ silent: [...silent] }),
      })
      message.success("工具配置已保存")
    } catch { message.error("保存失败") }
  }

  async function saveTtsConfig() {
    try {
      await fetch("/api/system-config", {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ tts_backend: ttsBackend }),
      })
      message.success("TTS 配置已保存")
    } catch { message.error("保存失败") }
  }

  function toggleTool(name: string, checked: boolean) {
    const next = new Set(silent)
    if (checked) { next.add(name) } else { next.delete(name) }
    setSilent(next)
  }

  const ttsTab = (
    <div>
      <Typography.Title level={5} style={{ marginBottom: 16 }}>TTS 语音后端</Typography.Title>
      <Radio.Group value={ttsBackend} onChange={e => setTtsBackend(e.target.value)}>
        <Radio.Button value="vits" style={{ marginBottom: 8 }}>VITS（本地 Paimon 音色）</Radio.Button>
        <br />
        <Radio.Button value="http">HTTP（外部 EasyVoice API）</Radio.Button>
      </Radio.Group>
      <div style={{ marginTop: 16 }}>
        <Button type="primary" icon={<SaveOutlined />} onClick={saveTtsConfig}>保存</Button>
      </div>
    </div>
  )

  const toolsTab = (
    <div>
      <Typography.Title level={5} style={{ marginBottom: 16 }}>TTS 提示语静默</Typography.Title>
      <Typography.Text type="secondary" style={{ marginBottom: 8, display: "block" }}>
        打开开关 = 该工具调用时不播 TTS 提示语（如"让我查一下"）
      </Typography.Text>
      <Spin spinning={loading}>
        {tools.map(t => (
          <div key={t.name} style={{ display: "flex", alignItems: "center", gap: 12, padding: "6px 0", borderBottom: "1px solid #f0f0f0" }}>
            <Switch size="small" checked={silent.has(t.name)} onChange={v => toggleTool(t.name, v)} />
            <Typography.Text code style={{ width: 200, fontSize: 12, whiteSpace: "nowrap", flexShrink: 0 }}>{t.name}</Typography.Text>
            <Typography.Text type="secondary" style={{ fontSize: 12, flex: 1 }}>{t.description}</Typography.Text>
          </div>
        ))}
      </Spin>
      <div style={{ marginTop: 16 }}>
        <Button type="primary" icon={<SaveOutlined />} onClick={saveToolConfig}>保存</Button>
      </div>
    </div>
  )

  return (
    <Modal
      title="系统配置"
      open={open}
      onCancel={onClose}
      footer={null}
      width={700}
    >
      <Tabs items={[
        { key: "tts", label: "TTS 后端", children: ttsTab },
        { key: "tools", label: "工具配置", children: toolsTab },
      ]} />
    </Modal>
  )
}
