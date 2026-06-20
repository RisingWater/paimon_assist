import { useEffect, useState } from "react"
import { Layout, Tabs, Typography, App, Button } from "antd"
import { UserOutlined, AudioOutlined, MessageOutlined, ClockCircleOutlined, BookOutlined, SettingOutlined, SaveOutlined, FileTextOutlined, SoundOutlined } from "@ant-design/icons"
import { api, type User } from "./api"
import UserTab from "./components/UserTab"
import VoiceprintTab from "./components/VoiceprintTab"
import ChatTab from "./components/ChatTab"
import ReminderTab from "./components/ReminderTab"
import MemoryTab from "./components/MemoryTab"
import SystemConfigModal from "./components/SystemConfigModal"
import CacheTab from "./components/CacheTab"
import BackupTab from "./components/BackupTab"
import LogTab from "./components/LogTab"
import WakewordTab from "./components/WakewordTab"

const { Header, Content } = Layout

export default function Root() {
  const { message } = App.useApp()
  const [users, setUsers] = useState<User[]>([])
  const [loading, setLoading] = useState(true)
  const [cfgOpen, setCfgOpen] = useState(false)

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
    {
      key: "cache",
      label: <span><AudioOutlined /> TTS 缓存</span>,
      children: <CacheTab />,
    },
    {
      key: "backup",
      label: <span><SaveOutlined /> 备份恢复</span>,
      children: <BackupTab />,
    },
    {
      key: "logs",
      label: <span><FileTextOutlined /> 系统日志</span>,
      children: <LogTab />,
    },
    {
      key: "wakeword",
      label: <span><SoundOutlined /> 唤醒词收集</span>,
      children: <WakewordTab />,
    },
  ]

  return (
    <Layout style={{ minHeight: "100vh", background: "#f5f5f5" }}>
      <Header style={{ display: "flex", alignItems: "center", gap: 16, background: "#fff", borderBottom: "1px solid #f0f0f0", padding: "0 40px" }}>
        <Typography.Title level={4} style={{ color: "#1677ff", margin: 0, whiteSpace: "nowrap" }}>
          派萌助手
        </Typography.Title>
        <Typography.Text type="secondary">管理后台</Typography.Text>
        <div style={{ flex: 1 }} />
        <Button type="text" icon={<SettingOutlined />} onClick={() => setCfgOpen(true)} />
      </Header>
      <Content style={{ maxWidth: 1200, width: "100%", margin: "24px auto", padding: "0 20px" }}>
        <Tabs defaultActiveKey="users" items={tabs} />
      </Content>
      <SystemConfigModal open={cfgOpen} onClose={() => setCfgOpen(false)} />
    </Layout>
  )
}
