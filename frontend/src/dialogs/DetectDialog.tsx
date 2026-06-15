import { useState, useRef } from "react"
import { Modal, Button, App, Card, Tag, Space, Typography } from "antd"
import { AudioOutlined } from "@ant-design/icons"
import { api, type DetectResult } from "../api"

export default function DetectDialog({ open, onClose }: { open: boolean; onClose: () => void }) {
  const { message } = App.useApp()
  const [recording, setRecording] = useState(false)
  const [analyzing, setAnalyzing] = useState(false)
  const [result, setResult] = useState<DetectResult | null>(null)
  const recorderRef = useRef<MediaRecorder | null>(null)

  async function toggleRecord() {
    if (recording) {
      recorderRef.current?.stop()
      setAnalyzing(true)
      return
    }
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true })
      const mr = new MediaRecorder(stream, { mimeType: "audio/webm" })
      const chunks: BlobPart[] = []
      mr.ondataavailable = (e) => chunks.push(e.data)
      mr.onstop = async () => {
        const blob = new Blob(chunks, { type: "audio/webm" })
        stream.getTracks().forEach((t) => t.stop())
        setRecording(false)
        try {
          const data = await api.detect(blob)
          setResult(data)
        } catch {
          message.error("检测失败")
        } finally {
          setAnalyzing(false)
        }
      }
      mr.start()
      recorderRef.current = mr
      setRecording(true)
      setResult(null)
    } catch {
      message.error("无法访问麦克风")
    }
  }

  function close() {
    if (recording) recorderRef.current?.stop()
    setRecording(false)
    setAnalyzing(false)
    setResult(null)
    onClose()
  }

  const statusText = recording
    ? "正在录音..."
    : analyzing
      ? "正在分析..."
      : result
        ? (result.best_uid
            ? `识别结果: ${result.best_name || "用户#" + result.best_uid} (sim=${result.best_avg.toFixed(4)})`
            : "未匹配到任何人")
        : "录一段声音，检测是谁"

  return (
    <Modal
      title="声纹检测"
      open={open}
      onCancel={close}
      footer={<Button onClick={close}>关闭</Button>}
      width={560}
    >
      <Space direction="vertical" style={{ width: "100%" }} size="middle">
        <Space>
          <Button
            type="primary"
            icon={<AudioOutlined />}
            danger={recording}
            onClick={toggleRecord}
            loading={analyzing}
          >
            {recording ? "停止" : "录音"}
          </Button>
          <Typography.Text style={{ color: "#888", fontSize: 13 }}>{statusText}</Typography.Text>
        </Space>

        {result && (
          <div style={{ maxHeight: "50vh", overflow: "auto" }}>
            {result.users.map((ug) => {
              const dn = ug.name || `用户#${ug.user_id}`
              return (
                <Card key={ug.user_id} size="small" style={{ marginBottom: 8 }}>
                  <Typography.Text strong>{dn}</Typography.Text>
                  <Typography.Text style={{ marginLeft: 8 }} type="secondary">
                    avg={ug.avg_sim.toFixed(4)}
                  </Typography.Text>
                  <div style={{ marginTop: 4 }}>
                    <Space wrap>
                      {ug.voiceprints.map((vp) => (
                        <Tag key={vp.id} color={vp.sim > 0.5 ? "green" : "default"}>
                          #{vp.id}: {vp.sim.toFixed(4)}
                        </Tag>
                      ))}
                    </Space>
                  </div>
                </Card>
              )
            })}
          </div>
        )}
      </Space>
    </Modal>
  )
}
