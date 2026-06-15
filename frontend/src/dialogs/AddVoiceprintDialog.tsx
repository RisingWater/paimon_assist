import { useState, useRef } from "react"
import { Modal, Select, Button, Upload, App, Space } from "antd"
import { AudioOutlined, UploadOutlined } from "@ant-design/icons"
import { api, type User } from "../api"

export default function AddVoiceprintDialog({
  open,
  users,
  onClose,
  onAdded,
}: {
  open: boolean
  users: User[]
  onClose: () => void
  onAdded: () => void
}) {
  const { message } = App.useApp()
  const [userId, setUserId] = useState<number | undefined>()
  const [recording, setRecording] = useState(false)
  const [blob, setBlob] = useState<Blob | null>(null)
  const recorderRef = useRef<MediaRecorder | null>(null)

  async function toggleRecord() {
    if (recording) {
      recorderRef.current?.stop()
      return
    }
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true })
      const mr = new MediaRecorder(stream, { mimeType: "audio/webm" })
      const chunks: BlobPart[] = []
      mr.ondataavailable = (e) => chunks.push(e.data)
      mr.onstop = () => {
        setBlob(new Blob(chunks, { type: "audio/webm" }))
        stream.getTracks().forEach((t) => t.stop())
        setRecording(false)
      }
      mr.start()
      recorderRef.current = mr
      setRecording(true)
      setBlob(null)
    } catch {
      message.error("无法访问麦克风")
    }
  }

  async function upload() {
    if (!userId) { message.warning("请选择目标用户"); return }
    if (!blob) { message.warning("请先录音或选择文件"); return }
    try {
      await api.addVoiceprint(userId, blob, "recording.webm")
      close()
      message.success("声纹已添加")
      onAdded()
    } catch {
      message.error("上传失败")
    }
  }

  function close() {
    if (recording) recorderRef.current?.stop()
    setRecording(false)
    setBlob(null)
    onClose()
  }

  return (
    <Modal title="添加声纹" open={open} onCancel={close} onOk={upload} okText="上传" cancelText="取消">
      <Space direction="vertical" style={{ width: "100%" }} size="middle">
        <div>
          <div style={{ marginBottom: 4, fontSize: 13, color: "#888" }}>目标用户</div>
          <Select
            style={{ width: "100%" }}
            placeholder="选择用户..."
            value={userId}
            onChange={setUserId}
            options={users.map((u) => ({
              value: u.id,
              label: u.name || `用户#${u.id}`,
            }))}
          />
        </div>
        <div>
          <Button
            type="primary"
            icon={<AudioOutlined />}
            danger={recording}
            onClick={toggleRecord}
          >
            {recording ? "停止录音" : "开始录音"}
          </Button>
          <span style={{ marginLeft: 12, color: "#888", fontSize: 13 }}>
            {recording ? "正在录音..." : blob ? "录音完成，点击上传提交" : "点击按钮开始录音"}
          </span>
        </div>
        <Upload
          accept=".wav"
          maxCount={1}
          beforeUpload={(file) => {
            setBlob(file)
            return false
          }}
        >
          <Button icon={<UploadOutlined />}>选择 WAV 文件</Button>
        </Upload>
      </Space>
    </Modal>
  )
}
