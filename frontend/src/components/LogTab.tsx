import { useEffect, useState, useCallback, useRef } from "react"
import { Button, Select, Input, Table, Typography, App, Popconfirm, Tag, Space, Switch } from "antd"
import { DeleteOutlined, DownloadOutlined, ReloadOutlined, SyncOutlined } from "@ant-design/icons"
import { api, type LogEntry } from "../api"

const LEVEL_COLORS: Record<string, string> = {
  DEBUG: "default",
  INFO: "blue",
  WARNING: "orange",
  ERROR: "red",
  CRITICAL: "magenta",
}

const LEVEL_OPTIONS = [
  { value: "", label: "全部级别" },
  { value: "DEBUG", label: "DEBUG" },
  { value: "INFO", label: "INFO" },
  { value: "WARNING", label: "WARNING" },
  { value: "ERROR", label: "ERROR" },
  { value: "CRITICAL", label: "CRITICAL" },
]

const PAGE_SIZE = 50

export default function LogTab() {
  const { message } = App.useApp()
  const [logs, setLogs] = useState<LogEntry[]>([])
  const [total, setTotal] = useState(0)
  const [loading, setLoading] = useState(false)
  const [level, setLevel] = useState("")
  const [search, setSearch] = useState("")
  const [page, setPage] = useState(1)
  const [autoRefresh, setAutoRefresh] = useState(false)
  const timerRef = useRef<ReturnType<typeof setInterval> | null>(null)

  const load = useCallback(async (p?: number) => {
    setLoading(true)
    try {
      const offset = ((p ?? page) - 1) * PAGE_SIZE
      const res = await api.getLogs({ level: level || undefined, search: search || undefined, limit: PAGE_SIZE, offset })
      setLogs(res.logs)
      setTotal(res.total)
    } catch {
      message.error("加载日志失败")
    } finally {
      setLoading(false)
    }
  }, [level, search, page])

  // 首次加载
  useEffect(() => { load(1) }, [])
  // 筛选条件变化时回到第一页
  useEffect(() => { setPage(1); load(1) }, [level, search])

  // 自动刷新
  useEffect(() => {
    if (autoRefresh) {
      timerRef.current = setInterval(() => load(), 2000)
      return () => { if (timerRef.current) clearInterval(timerRef.current) }
    } else {
      if (timerRef.current) { clearInterval(timerRef.current); timerRef.current = null }
    }
  }, [autoRefresh, load])

  async function handleClear() {
    try {
      await api.clearLogs()
      setLogs([])
      setTotal(0)
      message.success("日志已清空")
    } catch {
      message.error("清空失败")
    }
  }

  function handleSearch(value: string) {
    setSearch(value)
  }

  const columns = [
    {
      title: "时间", dataIndex: "time", width: 170,
      render: (v: string) => <Typography.Text code style={{ fontSize: 12 }}>{v}</Typography.Text>,
    },
    {
      title: "级别", dataIndex: "level", width: 80,
      render: (v: string) => <Tag color={LEVEL_COLORS[v] || "default"}>{v}</Tag>,
    },
    { title: "来源", dataIndex: "name", width: 140, ellipsis: true },
    { title: "消息", dataIndex: "message", ellipsis: true,
      render: (v: string) => (
        <Typography.Text style={{ fontSize: 12, whiteSpace: "pre-wrap", wordBreak: "break-all" }}>
          {v}
        </Typography.Text>
      ),
    },
  ]

  const errorCount = logs.filter(l => l.level === "ERROR" || l.level === "CRITICAL").length

  return (
    <div>
      {/* Top bar */}
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 16, flexWrap: "wrap", gap: 8 }}>
        <Space>
          <Typography.Text type="secondary">
            共 {total} 条
            {errorCount > 0 && (
              <Typography.Text type="danger">（含 {errorCount} 条错误）</Typography.Text>
            )}
          </Typography.Text>
          <Typography.Text type="secondary" style={{ fontSize: 12 }}>
            （磁盘持久化，上限 20MB）
          </Typography.Text>
        </Space>
        <Space>
          <span>
            <SyncOutlined spin={autoRefresh} style={{ marginRight: 4, color: autoRefresh ? "#1677ff" : "#999" }} />
            <Switch size="small" checked={autoRefresh} onChange={setAutoRefresh} />
            <Typography.Text type="secondary" style={{ marginLeft: 4, fontSize: 12 }}>自动刷新</Typography.Text>
          </span>
          <Button icon={<ReloadOutlined />} onClick={() => load()} loading={loading} size="small">
            刷新
          </Button>
          <Button icon={<DownloadOutlined />} href={api.exportLogsUrl()} size="small">
            导出
          </Button>
          <Popconfirm title="确定清空全部日志？" onConfirm={handleClear}>
            <Button danger icon={<DeleteOutlined />} size="small">清空</Button>
          </Popconfirm>
        </Space>
      </div>

      {/* Filters */}
      <div style={{ display: "flex", gap: 8, marginBottom: 16 }}>
        <Select
          value={level}
          onChange={setLevel}
          options={LEVEL_OPTIONS}
          style={{ width: 120 }}
          size="small"
        />
        <Input.Search
          placeholder="搜索日志内容…"
          value={search}
          onChange={e => setSearch(e.target.value)}
          onSearch={handleSearch}
          style={{ flex: 1, maxWidth: 400 }}
          size="small"
          allowClear
        />
      </div>

      {/* Table */}
      <Table
        dataSource={logs}
        rowKey="id"
        size="small"
        loading={loading && !autoRefresh}
        pagination={{
          current: page,
          pageSize: PAGE_SIZE,
          total,
          showTotal: (t) => `共 ${t} 条`,
          onChange: (p) => { setPage(p); load(p) },
          showSizeChanger: false,
        }}
        columns={columns}
        locale={{ emptyText: "暂无日志" }}
        onRow={(record) => {
          if (record.level === "ERROR" || record.level === "CRITICAL") {
            return { style: { background: "#fff2f0" } }
          }
          return {}
        }}
      />
    </div>
  )
}
