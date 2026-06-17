import { useEffect, useState } from "react"
import { Button, Space, Typography, Table, Select, Input, App, Popconfirm, Tag, Empty } from "antd"
import { PlusOutlined, DeleteOutlined } from "@ant-design/icons"
import { api, type Reminder } from "../api"

export default function ReminderTab() {
  const { message } = App.useApp()
  const [reminders, setReminders] = useState<Reminder[]>([])
  const [loading, setLoading] = useState(true)
  const [adding, setAdding] = useState(false)
  const [newContent, setNewContent] = useState("")
  const [newType, setNewType] = useState("once")
  const [newDT, setNewDT] = useState("")
  const [newLunar, setNewLunar] = useState(false)

  async function load() {
    setLoading(true)
    try {
      setReminders(await api.listReminders())
    } catch { message.error("加载失败") }
    finally { setLoading(false) }
  }

  useEffect(() => { load() }, [])

  async function handleAdd() {
    if (!newContent.trim() || !newDT.trim()) { message.warning("请填写内容和时间"); return }
    try {
      await api.addReminder({ content: newContent.trim(), rtype: newType, datetime: newDT.trim(), lunar: newLunar })
      message.success("已添加")
      setAdding(false); setNewContent(""); setNewDT(""); setNewLunar(false)
      load()
    } catch { message.error("添加失败") }
  }

  async function handleDelete(id: number) {
    await api.deleteReminder(id)
    message.success("已删除")
    load()
  }

  const typeLabel: Record<string, string> = { once: "一次性", daily: "每天", monthly: "每月" }
  const typeColor: Record<string, string> = { once: "blue", daily: "green", monthly: "orange" }

  return (
    <div>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 16 }}>
        <Typography.Text type="secondary">共 {reminders.length} 条提醒</Typography.Text>
        <Button icon={<PlusOutlined />} onClick={() => setAdding(true)}>添加提醒</Button>
      </div>

      {adding && (
        <div style={{ background: "#f5f5f5", padding: 12, borderRadius: 6, marginBottom: 16 }}>
          <Space wrap>
            <Input placeholder="提醒内容" value={newContent} onChange={e => setNewContent(e.target.value)} style={{ width: 200 }} />
            <Select value={newType} onChange={setNewType} style={{ width: 100 }}
              options={[{ value: "once", label: "一次性" }, { value: "daily", label: "每天" }, { value: "monthly", label: "每月" }]}
            />
            <Input placeholder={newType === "daily" ? "21:00" : newType === "monthly" ? "15 21:00" : "2026-06-18 21:00"} value={newDT} onChange={e => setNewDT(e.target.value)} style={{ width: 180 }} />
            {newType === "monthly" && (
              <Select value={newLunar ? 1 : 0} onChange={v => setNewLunar(!!v)} style={{ width: 80 }}
                options={[{ value: 0, label: "公历" }, { value: 1, label: "农历" }]}
              />
            )}
            <Button type="primary" onClick={handleAdd}>确认</Button>
            <Button onClick={() => setAdding(false)}>取消</Button>
          </Space>
        </div>
      )}

      {!loading && reminders.length === 0 ? (
        <Empty description="还没有定时提醒" />
      ) : (
        <Table
          dataSource={reminders}
          rowKey="id"
          size="small"
          loading={loading}
          pagination={{ pageSize: 20 }}
          columns={[
            { title: "#", dataIndex: "id", width: 50 },
            { title: "内容", dataIndex: "content" },
            {
              title: "类型", dataIndex: "rtype", width: 100,
              render: (t: string) => <Tag color={typeColor[t]}>{typeLabel[t] || t}</Tag>,
            },
            {
              title: "时间", dataIndex: "datetime", width: 180,
              render: (v: string, r: Reminder) => (r.lunar ? "农历 " : "") + v,
            },
            {
              title: "状态", dataIndex: "done", width: 80,
              render: (d: boolean) => d ? <Tag color="green">已完成</Tag> : <Tag>进行中</Tag>,
            },
            {
              title: "操作", key: "actions", width: 80,
              render: (_: unknown, r: Reminder) => (
                <Popconfirm title="删除？" onConfirm={() => handleDelete(r.id)}>
                  <Button size="small" danger icon={<DeleteOutlined />} />
                </Popconfirm>
              ),
            },
          ]}
        />
      )}
    </div>
  )
}
