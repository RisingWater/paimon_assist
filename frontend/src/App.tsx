import { useEffect, useState } from "react"
import { Layout, Tabs, Typography, App, Button, Select, Grid } from "antd"
import { UserOutlined, AudioOutlined, MessageOutlined, ClockCircleOutlined, BookOutlined, SettingOutlined, SaveOutlined, FileTextOutlined, SoundOutlined, DashboardOutlined } from "@ant-design/icons"
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
import MemoryMonitorTab from "./components/MemoryMonitorTab"

const { Header, Content } = Layout
const { useBreakpoint } = Grid

export default function Root() {
  const { message } = App.useApp()
  const screens = useBreakpoint()
  const isMobile = !screens.md
  const [users, setUsers] = useState<User[]>([])
  const [loading, setLoading] = useState(true)
  const [cfgOpen, setCfgOpen] = useState(false)
  const [activeTab, setActiveTab] = useState("users")

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
    { key: "users",      label: "用户管理",   icon: <UserOutlined />,        children: <UserTab users={users} loading={loading} onRefresh={loadData} /> },
    { key: "voiceprints",label: "声纹管理",   icon: <AudioOutlined />,       children: <VoiceprintTab users={users} loading={loading} onRefresh={loadData} /> },
    { key: "chat",       label: "聊天历史",   icon: <MessageOutlined />,     children: <ChatTab users={users} /> },
    { key: "reminders",  label: "定时提醒",   icon: <ClockCircleOutlined />, children: <ReminderTab /> },
    { key: "memory",     label: "记忆管理",   icon: <BookOutlined />,        children: <MemoryTab users={users} /> },
    { key: "cache",      label: "TTS 缓存",   icon: <AudioOutlined />,       children: <CacheTab /> },
    { key: "backup",     label: "备份恢复",   icon: <SaveOutlined />,        children: <BackupTab /> },
    { key: "logs",       label: "系统日志",   icon: <FileTextOutlined />,    children: <LogTab /> },
    { key: "wakeword",   label: "唤醒词收集", icon: <SoundOutlined />,       children: <WakewordTab /> },
    { key: "memory-monitor", label: "内存监控", icon: <DashboardOutlined />, children: <MemoryMonitorTab /> },
  ]

  const activeContent = tabs.find(t => t.key === activeTab)?.children

  return (
    <Layout style={{ minHeight: "100vh", background: "#f5f5f5" }}>
      <Header style={{
        display: "flex", alignItems: "center", gap: isMobile ? 8 : 16,
        background: "#fff", borderBottom: "1px solid #f0f0f0",
        padding: isMobile ? "0 12px" : "0 40px",
      }}>
        <Typography.Title level={isMobile ? 5 : 4} style={{ color: "#1677ff", margin: 0, whiteSpace: "nowrap" }}>
          派萌助手
        </Typography.Title>
        {!isMobile && <Typography.Text type="secondary">管理后台</Typography.Text>}
        <div style={{ flex: 1 }} />
        {isMobile ? (
          <Select
            value={activeTab}
            onChange={setActiveTab}
            style={{ width: 130 }}
            size="small"
            options={tabs.map(t => ({ value: t.key, label: t.label }))}
          />
        ) : null}
        <Button type="text" icon={<SettingOutlined />} onClick={() => setCfgOpen(true)} />
      </Header>
      <Content style={{
        maxWidth: isMobile ? "100%" : 1200, width: "100%",
        margin: isMobile ? "12px auto" : "24px auto",
        padding: isMobile ? "0 8px" : "0 20px",
      }}>
        {isMobile ? (
          activeContent
        ) : (
          <Tabs activeKey={activeTab} onChange={setActiveTab} items={tabs.map(t => ({
            key: t.key,
            label: <span>{t.icon} {t.label}</span>,
            children: t.children,
          }))} />
        )}
      </Content>
      <SystemConfigModal open={cfgOpen} onClose={() => setCfgOpen(false)} />
    </Layout>
  )
}
