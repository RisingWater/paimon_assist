import { useEffect, useState, useCallback } from "react"
import { Card, Button, Table, Switch, Space, Tag, message, Statistic, Row, Col } from "antd"
import { ReloadOutlined, DeleteOutlined } from "@ant-design/icons"

// ---- 类型 ----

interface MemoryItem {
  name: string
  size_mb: number
  size_bytes: number
  category: string
  description?: string
}

interface MemoryReport {
  total_rss: number
  total_rss_mb: number
  models: MemoryItem[]
  components: MemoryItem[]
  tracemalloc: MemoryItem[]
  summary: MemoryItem[]
  gc_stats: { collections?: number; collected?: number }[]
  timestamp: number
}

interface GcResult {
  collected: number
  before_mb: number
  after_mb: number
  freed_mb: number
}

// ---- 颜色 ----
const COLORS = [
  "#1677ff", "#52c41a", "#fa8c16", "#eb2f96", "#722ed1",
  "#13c2c2", "#f5222d", "#faad14", "#2f54eb", "#a0d911",
  "#f759ab", "#595959", "#8c8c8c", "#b37feb", "#5cdbd3",
]

// ---- SVG Donut 工具 ----

function polarToCartesian(cx: number, cy: number, r: number, angleDeg: number) {
  const rad = ((angleDeg - 90) * Math.PI) / 180
  return { x: cx + r * Math.cos(rad), y: cy + r * Math.sin(rad) }
}

function describeArc(
  cx: number, cy: number, outerR: number, innerR: number,
  startAngle: number, endAngle: number
) {
  const sOuter = polarToCartesian(cx, cy, outerR, endAngle)
  const eOuter = polarToCartesian(cx, cy, outerR, startAngle)
  const sInner = polarToCartesian(cx, cy, innerR, endAngle)
  const eInner = polarToCartesian(cx, cy, innerR, startAngle)
  const largeArc = endAngle - startAngle > 180 ? 1 : 0
  return [
    `M ${sOuter.x} ${sOuter.y}`,
    `A ${outerR} ${outerR} 0 ${largeArc} 0 ${eOuter.x} ${eOuter.y}`,
    `L ${eInner.x} ${eInner.y}`,
    `A ${innerR} ${innerR} 0 ${largeArc} 1 ${sInner.x} ${sInner.y}`,
    "Z",
  ].join(" ")
}

function DonutChart({ data, totalMb }: { data: MemoryItem[], totalMb: number }) {
  const cx = 110, cy = 110, outerR = 95, innerR = 55
  let cum = -90
  const total = data.reduce((s, d) => s + d.size_mb, 0) || 1

  return (
    <svg viewBox="0 0 220 220" style={{ width: "100%", maxWidth: 280 }}>
      {data.map((item, i) => {
        const angle = (item.size_mb / total) * 360
        const path = describeArc(cx, cy, outerR, innerR, cum, cum + angle)
        cum += angle
        return (
          <path key={item.name} d={path}
            fill={COLORS[i % COLORS.length]}
            stroke="#fff" strokeWidth="1.5"
          >
            <title>{item.name}: {item.size_mb.toFixed(1)} MB</title>
          </path>
        )
      })}
      <text x={cx} y={cy - 8} textAnchor="middle"
        fontSize="22" fontWeight="bold" fill="#333">
        {totalMb.toFixed(0)}
      </text>
      <text x={cx} y={cy + 14} textAnchor="middle"
        fontSize="13" fill="#999">
        MB
      </text>
    </svg>
  )
}

// ---- 主组件 ----

export default function MemoryMonitorTab() {
  const [report, setReport] = useState<MemoryReport | null>(null)
  const [loading, setLoading] = useState(false)
  const [autoRefresh, setAutoRefresh] = useState(false)
  const [gcResult, setGcResult] = useState<GcResult | null>(null)

  const fetchReport = useCallback(async () => {
    setLoading(true)
    try {
      const res = await fetch("/api/memory_track/report")
      const data = await res.json()
      setReport(data)
    } catch {
      message.error("获取内存报告失败")
    } finally {
      setLoading(false)
    }
  }, [])

  const doGc = useCallback(async () => {
    try {
      setGcResult(null)
      const res = await fetch("/api/memory_track/gc", { method: "POST" })
      const data = await res.json()
      setGcResult(data)
      message.success(`GC 回收了 ${data.collected} 个对象，释放 ${data.freed_mb} MB`)
      // 等 GC 完后刷新
      setTimeout(fetchReport, 500)
    } catch {
      message.error("GC 失败")
    }
  }, [fetchReport])

  useEffect(() => { fetchReport() }, [fetchReport])

  // 自动刷新
  useEffect(() => {
    if (!autoRefresh) return
    const timer = setInterval(fetchReport, 5000)
    return () => clearInterval(timer)
  }, [autoRefresh, fetchReport])

  // 合并详细列表
  const allItems: MemoryItem[] = report?.summary ?? []

  // 饼图数据（过滤掉碎片等占比过小的）
  const chartData = (report?.summary ?? []).filter(d => d.size_mb > 1)

  const columns = [
    { title: "模块", dataIndex: "name", key: "name",
      render: (_: string, r: MemoryItem) => (
        <Space>
          <span style={{
            display: "inline-block", width: 10, height: 10, borderRadius: 2,
            backgroundColor: COLORS[allItems.indexOf(r) % COLORS.length],
          }} />
          <span>{r.name}</span>
        </Space>
      ),
    },
    { title: "类别", dataIndex: "category", key: "category", width: 90,
      render: (c: string) => <Tag>{c}</Tag>,
    },
    { title: "内存", dataIndex: "size_mb", key: "size_mb", width: 100,
      render: (mb: number) => (
        <span style={{ fontWeight: 600, color: mb > 200 ? "#ff4d4f" : mb > 50 ? "#fa8c16" : "#52c41a" }}>
          {mb.toFixed(1)} MB
        </span>
      ),
    },
    { title: "占比", key: "percent", width: 70,
      render: (_: unknown, r: MemoryItem) => {
        const pct = report ? (r.size_mb / report.total_rss_mb * 100) : 0
        return `${pct.toFixed(1)}%`
      },
    },
  ]

  return (
    <div>
      {/* 顶部统计 + GC 按钮 */}
      <Row gutter={[12, 12]} style={{ marginBottom: 16 }}>
        <Col xs={12} sm={6}>
          <Card size="small">
            <Statistic title="进程总内存" value={report?.total_rss_mb ?? "-"}
              suffix="MB" precision={1} />
          </Card>
        </Col>
        <Col xs={12} sm={6}>
          <Card size="small">
            <Statistic title="模型数量" value={report?.models.length ?? "-"} />
          </Card>
        </Col>
        <Col xs={12} sm={6}>
          <Card size="small">
            <Statistic title="上次 GC 回收"
              value={gcResult ? `${gcResult.freed_mb} MB` : (report ? "—" : "-")}
              valueStyle={{ color: (gcResult?.freed_mb ?? 0) > 0 ? "#52c41a" : undefined }}
            />
          </Card>
        </Col>
        <Col xs={12} sm={6}>
          <Card size="small" style={{ display: "flex", alignItems: "center", gap: 8 }}>
            <Button type="primary" icon={<DeleteOutlined />} onClick={doGc} block>
              手动 GC
            </Button>
          </Card>
        </Col>
      </Row>

      {/* 饼图 + 自动刷新 */}
      <Card
        size="small"
        title="内存分布"
        extra={
          <Space>
            <Switch checked={autoRefresh} onChange={setAutoRefresh}
              checkedChildren="自动" unCheckedChildren="手动" />
            <Button size="small" icon={<ReloadOutlined />}
              onClick={fetchReport} loading={loading}>刷新</Button>
          </Space>
        }
        style={{ marginBottom: 16 }}
      >
        <div style={{ display: "flex", alignItems: "center", flexWrap: "wrap", gap: 24, justifyContent: "center" }}>
          {chartData.length > 0 && (
            <DonutChart data={chartData} totalMb={report?.total_rss_mb ?? 0} />
          )}
          {/* 图例 */}
          <div style={{ flex: 1, minWidth: 200, maxHeight: 260, overflow: "auto" }}>
            {chartData.map((d, i) => (
              <div key={d.name} style={{
                display: "flex", alignItems: "center", gap: 8,
                padding: "3px 0", fontSize: 13,
              }}>
                <span style={{
                  display: "inline-block", width: 12, height: 12, borderRadius: 3,
                  backgroundColor: COLORS[i % COLORS.length], flexShrink: 0,
                }} />
                <span style={{ flex: 1, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                  {d.name}
                </span>
                <span style={{ fontWeight: 500, whiteSpace: "nowrap" }}>
                  {d.size_mb.toFixed(1)} MB
                </span>
                <span style={{ color: "#999", fontSize: 12, whiteSpace: "nowrap" }}>
                  ({report ? (d.size_mb / report.total_rss_mb * 100).toFixed(1) : 0}%)
                </span>
              </div>
            ))}
          </div>
        </div>
      </Card>

      {/* 详细列表 */}
      <Card size="small" title="模块详情">
        <Table
          dataSource={allItems}
          columns={columns}
          rowKey="name"
          size="small"
          pagination={{ pageSize: 20, size: "small" }}
          locale={{ emptyText: "点击刷新获取数据" }}
        />
      </Card>
    </div>
  )
}
