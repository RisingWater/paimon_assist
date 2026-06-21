import { useEffect, useState } from "react"
import { Modal, Tabs, Radio, Typography, Button, Switch, App, Spin, Grid, TimePicker, Space, Tag } from "antd"
import { SaveOutlined } from "@ant-design/icons"
import dayjs, { type Dayjs } from "dayjs"

const { useBreakpoint } = Grid

interface ToolInfo {
  name: string
  description: string
  silent_default?: boolean
}

interface Props {
  open: boolean
  onClose: () => void
}

export default function SystemConfigModal({ open, onClose }: Props) {
  const { message } = App.useApp()
  const screens = useBreakpoint()
  const [ttsBackend, setTtsBackend] = useState("vits")
  const [tools, setTools] = useState<ToolInfo[]>([])
  const [silent, setSilent] = useState<Set<string>>(new Set())
  const [loading, setLoading] = useState(false)

  // 唤醒词配置
  const [wwEnabled, setWwEnabled] = useState(true)
  const [wwScheduleEnabled, setWwScheduleEnabled] = useState(false)
  const [wwStart, setWwStart] = useState<Dayjs>(dayjs("06:00", "HH:mm"))
  const [wwEnd, setWwEnd] = useState<Dayjs>(dayjs("24:00", "HH:mm"))

  useEffect(() => {
    if (!open) return
    setLoading(true)

    fetch("/api/tool-config").then(r => r.json()).then(data => {
      setTools(data.tools)
      setSilent(new Set(data.silent))
    }).catch(() => {})

    fetch("/api/system-config").then(r => r.json()).then(data => {
      setTtsBackend(data.tts_backend || "vits")
      setWwEnabled(data.wakeword_enabled !== false)
      setWwScheduleEnabled(data.wakeword_schedule_enabled === true)
      setWwStart(dayjs(data.wakeword_start || "06:00", "HH:mm"))
      setWwEnd(dayjs(data.wakeword_end || "24:00", "HH:mm"))
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

  async function saveWakewordConfig() {
    try {
      await fetch("/api/system-config", {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          wakeword_enabled: wwEnabled,
          wakeword_schedule_enabled: wwScheduleEnabled,
          wakeword_start: wwStart.format("HH:mm"),
          wakeword_end: wwEnd.format("HH:mm"),
        }),
      })
      message.success("唤醒词配置已保存")
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
            <Switch size="small" checked={silent.has(t.name) || !!t.silent_default} onChange={v => toggleTool(t.name, v)} />
            <Typography.Text code style={{ width: 200, fontSize: 12, whiteSpace: "nowrap", flexShrink: 0 }}>{t.name}</Typography.Text>
            {t.silent_default && <Tag color="blue" style={{ fontSize: 11, lineHeight: "18px" }}>默认</Tag>}
            <Typography.Text type="secondary" style={{ fontSize: 12, flex: 1 }}>{t.description}</Typography.Text>
          </div>
        ))}
      </Spin>
      <div style={{ marginTop: 16 }}>
        <Button type="primary" icon={<SaveOutlined />} onClick={saveToolConfig}>保存</Button>
      </div>
    </div>
  )

  const wakewordTab = (
    <div>
      <Typography.Title level={5} style={{ marginBottom: 16 }}>唤醒词控制</Typography.Title>
      <Spin spinning={loading}>
        {/* 总开关 */}
        <div style={{ display: "flex", alignItems: "center", gap: 16, marginBottom: 20, padding: "12px 0", borderBottom: "1px solid #f0f0f0" }}>
          <Typography.Text strong>总开关：</Typography.Text>
          <Switch checked={wwEnabled} onChange={setWwEnabled} />
          <Typography.Text type={wwEnabled ? "success" : "secondary"}>
            {wwEnabled ? "已开启" : "已关闭"}
          </Typography.Text>
          <Typography.Text type="secondary" style={{ fontSize: 12 }}>
            {wwEnabled ? "唤醒词正常工作" : "完全不响应唤醒词"}
          </Typography.Text>
        </div>

        {/* 定时开关 */}
        <div style={{ padding: "12px 0", marginBottom: 8 }}>
          <div style={{ display: "flex", alignItems: "center", gap: 16, marginBottom: 12 }}>
            <Typography.Text strong>定时唤醒：</Typography.Text>
            <Switch checked={wwScheduleEnabled} onChange={setWwScheduleEnabled} />
            <Typography.Text type={wwScheduleEnabled ? "success" : "secondary"}>
              {wwScheduleEnabled ? "已开启" : "已关闭"}
            </Typography.Text>
          </div>
          {wwScheduleEnabled && (
            <div style={{ marginLeft: 8 }}>
              <Space>
                <TimePicker value={wwStart} onChange={v => v && setWwStart(v)} format="HH:mm" size="small" />
                <Typography.Text>—</Typography.Text>
                <TimePicker value={wwEnd} onChange={v => v && setWwEnd(v)} format="HH:mm" size="small" />
              </Space>
              <Typography.Text type="secondary" style={{ display: "block", marginTop: 8, fontSize: 12 }}>
                只有在此时间段内才会响应唤醒词。支持跨天（如 22:00-06:00）。
              </Typography.Text>
            </div>
          )}
        </div>
      </Spin>
      <div style={{ marginTop: 16 }}>
        <Button type="primary" icon={<SaveOutlined />} onClick={saveWakewordConfig}>保存</Button>
      </div>
    </div>
  )

  return (
    <Modal
      title="系统配置"
      open={open}
      onCancel={onClose}
      footer={null}
      width={screens.xs ? "95%" : 700}
    >
      <Tabs items={[
        { key: "tts", label: "TTS 后端", children: ttsTab },
        { key: "tools", label: "工具配置", children: toolsTab },
        { key: "wakeword", label: "唤醒词", children: wakewordTab },
      ]} />
    </Modal>
  )
}
