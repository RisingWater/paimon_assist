import { useState } from "react"
import { Button, Upload, Typography, App, Space } from "antd"
import { DownloadOutlined, UploadOutlined } from "@ant-design/icons"

export default function BackupTab() {
  const { message } = App.useApp()
  const [restoring, setRestoring] = useState(false)

  async function handleExport() {
    const a = document.createElement("a")
    a.href = "/api/backup"
    a.download = "paimon_backup.zip"
    document.body.appendChild(a)
    a.click()
    a.remove()
    message.success("下载中...")
  }

  async function handleRestore(file: File) {
    setRestoring(true)
    try {
      const fd = new FormData()
      fd.append("file", file)
      const res = await fetch("/api/restore", { method: "POST", body: fd })
      if (res.ok) {
        message.success("已恢复，请重启服务生效")
      } else {
        message.error("恢复失败")
      }
    } catch { message.error("恢复失败") }
    finally { setRestoring(false) }
  }

  return (
    <div>
      <Typography.Title level={5}>备份与恢复</Typography.Title>
      <Typography.Paragraph type="secondary">
        导出包含数据库、记忆文件、录音、TTS缓存、配置文件。导入会覆盖当前所有数据，请谨慎操作。
      </Typography.Paragraph>
      <Space style={{ marginTop: 16 }}>
        <Button type="primary" icon={<DownloadOutlined />} size="large" onClick={handleExport}>
          导出全部数据
        </Button>
        <Upload accept=".zip" showUploadList={false} beforeUpload={file => { handleRestore(file); return false }}>
          <Button icon={<UploadOutlined />} size="large" loading={restoring} danger>
            导入 ZIP 恢复
          </Button>
        </Upload>
      </Space>
    </div>
  )
}
