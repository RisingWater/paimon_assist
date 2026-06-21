import { useEffect, useState } from "react"
import { Button, Upload, Typography, App, Table, Space, Popconfirm } from "antd"
import { PlusOutlined, DownloadOutlined, UploadOutlined, RollbackOutlined } from "@ant-design/icons"

interface Backup {
  filename: string
  size: number
}

export default function BackupTab() {
  const { message } = App.useApp()
  const [items, setItems] = useState<Backup[]>([])
  const [loading, setLoading] = useState(false)
  const [creating, setCreating] = useState(false)

  async function load() {
    setLoading(true)
    try {
      const res = await fetch("/api/backups")
      setItems(await res.json())
    } catch { message.error("加载失败") }
    finally { setLoading(false) }
  }

  useEffect(() => { load() }, [])

  async function handleCreate() {
    setCreating(true)
    try {
      await fetch("/api/backup", { method: "POST" })
      message.success("备份已创建")
      load()
    } catch { message.error("备份失败") }
    finally { setCreating(false) }
  }

  async function handleRestore(filename: string) {
    try {
      const res = await fetch(`/api/backups/${encodeURIComponent(filename)}/restore`, { method: "POST" })
      if (res.ok) message.success("已恢复，重启生效")
      else message.error("恢复失败")
    } catch { message.error("恢复失败") }
  }

  function fmtSize(bytes: number) {
    if (bytes < 1024) return bytes + " B"
    if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + " KB"
    return (bytes / (1024 * 1024)).toFixed(1) + " MB"
  }

  const columns = [
    { title: "文件名", dataIndex: "filename" },
    { title: "大小", dataIndex: "size", width: 100, render: (v: number) => fmtSize(v) },
    {
      title: "操作", key: "actions", width: 200,
      render: (_: unknown, r: Backup) => (
        <Space>
          <Button size="small" icon={<DownloadOutlined />}
            href={`/api/backups/${encodeURIComponent(r.filename)}`}>下载</Button>
          <Popconfirm title="从该备份恢复？将覆盖当前数据" onConfirm={() => handleRestore(r.filename)}>
            <Button size="small" icon={<RollbackOutlined />} danger>恢复</Button>
          </Popconfirm>
        </Space>
      ),
    },
  ]

  return (
    <div>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 16 }}>
        <Typography.Title level={5} style={{ margin: 0 }}>备份与恢复</Typography.Title>
        <Space>
          <Upload accept=".zip" showUploadList={false}
            beforeUpload={async file => {
              const fd = new FormData(); fd.append("file", file)
              await fetch("/api/backups/upload", { method: "POST", body: fd })
              message.success("已上传")
              load()
              return false
            }}>
            <Button icon={<UploadOutlined />}>上传备份</Button>
          </Upload>
          <Button type="primary" icon={<PlusOutlined />} onClick={handleCreate} loading={creating}>
            创建备份
          </Button>
        </Space>
      </div>

      <Typography.Paragraph type="secondary">
        备份包含数据库、录音、TTS缓存、记忆文件。从备份恢复需重启服务。
      </Typography.Paragraph>

      <Table dataSource={items} rowKey="filename" size="small" loading={loading}
        scroll={{ x: "max-content" }} pagination={{ pageSize: 20 }} columns={columns}
        locale={{ emptyText: "暂无备份，点击「创建备份」生成" }} />
    </div>
  )
}
