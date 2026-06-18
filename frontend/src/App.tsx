import { useEffect, useState } from "react"
import { Layout, Tabs, Typography, App } from "antd"
import { UserOutlined, AudioOutlined, MessageOutlined, ClockCircleOutlined, BookOutlined } from "@ant-design/icons"
import { api, type User } from "./api"
import UserTab from "./components/UserTab"
import VoiceprintTab from "./components/VoiceprintTab"
import ChatTab from "./components/ChatTab"
import ReminderTab from "./components/ReminderTab"
import MemoryTab from "./components/MemoryTab"

const { Header, Content } = Layout

export default function Root() {
  const { message } = App.useApp()
  const [users, setUsers] = useState<User[]>([])
  const [loading, setLoading] = useState(true)

  async function loadData() {
    setLoading(true)
    try {
      setUsers(await api.listUsers())
    } catch {
      message.error("API 连接失败")
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => { loadData() }, [])

  const tabs = [
    {
      key: "users",
      label: <span><UserOutlined /> 用户管理</span>,
      children: <UserTab users={users} loading={loading} onRefresh={loadData} />,
    },
    {
      key: "voiceprints",
      label: <span><AudioOutlined /> 声纹管理</span>,
      children: <VoiceprintTab users={users} loading={loading} onRefresh={loadData} />,
    },
    {
      key: "chat",
      label: <span><MessageOutlined /> 聊天历史</span>,
      children: <ChatTab users={users} />,
    },
    {
      key: "reminders",
      label: <span><ClockCircleOutlined /> 定时提醒</span>,
      children: <ReminderTab />,
    },
    {
      key: "memory",
      label: <span><BookOutlined /> 记忆管理</span>,
      children: <MemoryTab users={users} />,
    },
  ]

  return (
    <Layout style={{ minHeight: "100vh", background: "#f5f5f5" }}>
      <Header style={{ display: "flex", alignItems: "center", gap: 16, background: "#fff", borderBottom: "1px solid #f0f0f0", padding: "0 32px" }}>
        <Typography.Title level={4} style={{ color: "#1677ff", margin: 0, whiteSpace: "nowrap" }}>
          派萌助手
        </Typography.Title>
        <Typography.Text type="secondary">管理后台</Typography.Text>
      </Header>
      <Content style={{ maxWidth: 960, width: "100%", margin: "24px auto", padding: "0 20px" }}>
        <Tabs defaultActiveKey="users" items={tabs} />
      </Content>
    </Layout>
  )
}
