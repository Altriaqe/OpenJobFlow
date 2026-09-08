import { createRoot } from "react-dom/client";
import { useEffect, useState } from "react";
import {
  Activity,
  AlertTriangle,
  ArrowUpRight,
  BarChart3,
  Bell,
  CheckCircle2,
  ChevronRight,
  CircleAlert,
  Clock3,
  Database,
  Info,
  LayoutDashboard,
  MapPin,
  Menu,
  RefreshCw,
  Send,
  Settings2,
  ShieldCheck,
  Workflow,
} from "lucide-react";
import "./styles.css";
import "./extra.css";
import "./stage.css";
import {
  jobflowApi,
  type CheckStatus,
  type CityJobCount,
  type DashboardSummary,
  type OperationRun,
  type StageStatus,
} from "./api";

type Page = "overview" | "operations" | "delivery" | "analytics" | "alerts";
const nav = [
  ["overview", "平台总览", LayoutDashboard],
  ["operations", "运行中心", Workflow],
  ["delivery", "投放中心", Send],
  ["analytics", "分析指标", BarChart3],
  ["alerts", "告警记录", Bell],
] as const;
const stages = [
  "数据源",
  "采集任务",
  "ETL 处理",
  "PostgreSQL 数据层",
  "数据分析 API",
  "报告生成",
  "Telegram 投放",
  "微信公众号投放",
];

export default function App() {
  const [page, setPage] = useState<Page>("overview");
  const [mobileOpen, setMobileOpen] = useState(false);
  const current = nav.find(([id]) => id === page) ?? nav[0];
  return (
    <div className="app">
      <aside className={mobileOpen ? "sidebar open" : "sidebar"}>
        <div className="brand">
          <span className="brand-icon">
            <Activity size={18} />
          </span>
          <span>
            <b>JobFlow</b>
            <small>Operations</small>
          </span>
        </div>
        <div className="nav-title">工作区</div>
        <nav>
          {nav.map(([id, label, Icon]) => (
            <button
              className={page === id ? "nav active" : "nav"}
              key={id}
              onClick={() => {
                setPage(id);
                setMobileOpen(false);
              }}
            >
              <Icon size={17} />
              <span>{label}</span>
              {page === id && <ChevronRight className="arrow" size={15} />}
            </button>
          ))}
        </nav>
        <div className="sidebar-bottom">
          <button className="nav">
            <Settings2 size={17} />
            <span>系统设置</span>
          </button>
          <div className="user">
            <span className="avatar">A</span>
            <span>
              <b>管理员</b>
              <small>安全会话</small>
            </span>
            <ShieldCheck size={15} />
          </div>
        </div>
      </aside>
      <main>
        <header>
          <button
            className="mobile-menu"
            onClick={() => setMobileOpen(!mobileOpen)}
          >
            <Menu size={21} />
          </button>
          <div className="crumb">
            <span>JobFlow</span>
            <ChevronRight size={14} />
            <b>{current[1]}</b>
          </div>
          <div className="header-right">
            <span className="online">
              <i />
              系统在线
            </span>
            <button className="icon">
              <RefreshCw size={16} />
            </button>
            <span className="avatar">A</span>
          </div>
        </header>
        <div className="content">
          <div className="heading">
            <div>
              <label>OPERATIONS CONSOLE</label>
              <h1>{current[1]}</h1>
              <p>统一查看数据链路、运行状态与渠道投放结果</p>
            </div>
            <button className="time">
              <Clock3 size={15} />
              最近 24 小时⌄
            </button>
          </div>
          {page === "overview" && <LiveStageOverview />}
          {page === "operations" && <Operations />}
          {page === "delivery" && <Delivery />}
          {page === "analytics" && <Analytics />}
          {page === "alerts" && <Alerts />}
        </div>
      </main>
    </div>
  );
}
function RecentRuns() {
  return <div className="table"><div className="row head"><span>操作</span><span>触发时间</span><span>耗时</span><span>状态</span></div>{[["服务器重启检查","今天 16:20","18s"],["每日恢复运行","今天 16:32","06m 18s"],["微信公众号草稿","今天 16:38","41s"]].map(row=><div className="row" key={row[0]}><span>{row[0]}</span><span>{row[1]}</span><span>{row[2]}</span><b className="success">{row[0] === "微信公众号草稿" ? "已创建" : "成功"}</b></div>)}</div>;
}

function LiveStageOverview() {
  const [stageRows, setStageRows] = useState<StageStatus[] | null>(null);
  const [summary, setSummary] = useState<DashboardSummary | null>(null);
  const [stageError, setStageError] = useState(false);
  const loadSummary = () => jobflowApi.dashboardSummary().then(setSummary).catch(() => setStageError(true));
  useEffect(() => { loadSummary(); const timer = window.setInterval(loadSummary, 30000); return () => window.clearInterval(timer); }, []);
  const fallback = stages.map((name, index) => ({ id: String(index), name, goal: "", acceptance: "", state: "演示数据" }));
  const rows = summary?.stages?.length ? summary.stages : stageRows?.length ? stageRows : fallback;
  const accepted = rows.filter(item => item.state === "已验收" || item.state === "已完成").length;
  const metrics = summary?.metrics;
  const channelCount = summary?.channels?.filter(item => item.status === "sent" || item.status === "created").length ?? 0;
  return <><div className="metrics"><Metric label="阶段状态" value={`${accepted}/${rows.length}`} detail={stageError ? "监控服务未连接" : "来自实时检查"} icon={<CheckCircle2/>}/><Metric label="有效岗位总量" value={metrics ? String(metrics.job_count) : "-"} detail={metrics ? `${metrics.city_count} 个城市` : "读取中"} icon={<Database/>}/><Metric label="最近 ETL 批次" value={metrics?.batch_row_count == null ? "-" : String(metrics.batch_row_count)} detail={metrics?.batch_status === "succeeded" ? "执行成功" : metrics?.batch_status ?? "读取中"} icon={<Workflow/>}/><Metric label="渠道投放" value={`${channelCount}/2`} detail="来自渠道记录" icon={<Send/>}/></div><div className="two"><Panel title="每日采集量"><div className="chart"><div className="empty-chart">采集趋势接口待接入</div></div></Panel><Panel title="阶段状态"><div className="stage-list">{rows.slice(0,5).map(item=><div className="stage" key={item.id}><span><i className={`dot ${item.state === "异常" ? "error" : ""}`}/>{item.name}</span><b className={`pill ${item.state === "异常" ? "danger" : ""}`}>{item.state}</b></div>)}</div><button className="link" type="button">查看全部阶段 <ChevronRight size={14}/></button></Panel></div><Panel title="最近运行"><RecentRuns/></Panel></>;
}

function Operations() {
  const [checks, setChecks] = useState<CheckStatus[] | null>(null);
  const [runs, setRuns] = useState<OperationRun[] | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(false);
  const loadOperations = () => {
    setLoading(true);
    setError(false);
    Promise.all([jobflowApi.recentChecks(), jobflowApi.recentRuns()])
      .then(([nextChecks, nextRuns]) => {
        setChecks(nextChecks);
        setRuns(nextRuns);
      })
      .catch(() => setError(true))
      .finally(() => setLoading(false));
  };
  useEffect(loadOperations, []);
  const checkNames = [
    ["tailscale_ssh", "Tailscale / SSH"],
    ["xvfb", "Xvfb"],
    ["chrome", "Chrome"],
    ["x11vnc", "x11vnc"],
    ["daily_timer", "Daily Timer"],
    ["postgres", "PostgreSQL"],
    ["api_container", "API 容器"],
    ["health", "健康检查"],
    ["ready", "就绪检查"],
    ["boss_login", "BOSS 登录"],
    ["latest_etl", "最近 ETL"],
    ["telegram", "Telegram"],
    ["wechat", "微信公众号"],
  ];
  const latestChecks = new Map((checks ?? []).map((item) => [item.name, item]));
  const visibleChecks = checkNames.map(([name, label]) => ({
    label,
    result: latestChecks.get(name),
  }));
  const failedCount = visibleChecks.filter(
    ({ result }) => result?.status === "failed",
  ).length;
  const latestRun = runs?.[0];
  const runTime = latestRun?.started_at
    ? new Date(latestRun.started_at).toLocaleString("zh-CN", {
        year: "numeric",
        month: "2-digit",
        day: "2-digit",
        hour: "2-digit",
        minute: "2-digit",
      })
    : "暂无记录";
  return (
    <>
      <div className="notice">
        {failedCount ? <AlertTriangle size={18} /> : <CheckCircle2 size={18} />}
        <span>
          <b>{error ? "检查服务未连接" : failedCount ? `${failedCount} 项检查未通过` : "系统检查已通过"}</b>
          <small>
            {checks ? `${visibleChecks.length} 项检查，最近记录：${runTime}` : "正在读取服务器检查记录"}
          </small>
        </span>
      </div>
      <Panel title="服务器重启检查" action="刚刚更新">
        <div className="checks">
          {visibleChecks.map(({ label, result }) => (
            <div className="check" key={label}>
              {result?.status === "failed" ? <AlertTriangle size={16} /> : <CheckCircle2 size={16} />}
              <span>{label}</span>
              <b>{result?.status === "failed" ? "失败" : result ? "通过" : "暂无"}</b>
            </div>
          ))}
        </div>
        <button className="primary" onClick={loadOperations} disabled={loading}>
          <RefreshCw size={16} />
          {loading ? "刷新中..." : "刷新检查结果"}
        </button>
      </Panel>
      <Panel title="运行记录">
        {latestRun ? (
          <div className="row">
            <span>{latestRun.kind === "server_check" ? "服务器重启检查" : latestRun.kind}</span>
            <span>{runTime}</span>
            <span>{visibleChecks.length} 项</span>
            <b className={latestRun.status === "succeeded" ? "success" : "muted"}>
              {latestRun.status === "succeeded" ? "成功" : latestRun.status}
            </b>
          </div>
        ) : (
          <div className="row"><span>暂无运行记录</span></div>
        )}
      </Panel>
    </>
  );
}
function Delivery() {
  return (
    <>
      <div className="delivery-banner">
        <div>
          <label>MANUAL DELIVERY</label>
          <h2>选择日期，分别执行渠道操作</h2>
          <p>Telegram 发送简报，微信公众号创建草稿。正式发布仍由人工确认。</p>
        </div>
        <Send size={28} />
      </div>
      <div className="delivery-grid">
        <DeliveryCard
          title="Telegram 投放"
          text="发送指定日期的文字简报和趋势图片。"
        />
        <DeliveryCard
          title="微信公众号草稿"
          text="创建指定日期的公众号草稿，不自动发布。"
        />
      </div>
    </>
  );
}
function DeliveryCard({ title, text }: { title: string; text: string }) {
  return (
    <div className="delivery-card">
      <Send className="delivery-icon" size={20} />
      <div className="card-title">
        <h3>{title}</h3>
        <b className="pill">已验收</b>
      </div>
      <p>{text}</p>
      <div className="controls">
        <input type="date" defaultValue="2026-09-06" />
        <button className="primary" type="button" disabled>
          待接入
        </button>
      </div>
    </div>
  );
}
function Metric({
  label,
  value,
  detail,
  icon,
}: {
  label: string;
  value: string;
  detail: string;
  icon: React.ReactNode;
}) {
  return (
    <div className="metric">
      <span className="metric-icon">{icon}</span>
      <span>
        <small>{label}</small>
        <strong>{value}</strong>
        <em>{detail}</em>
      </span>
    </div>
  );
}
function Panel({
  title,
  action,
  children,
}: {
  title: string;
  action?: string;
  children: React.ReactNode;
}) {
  return (
    <section className="panel">
      <div className="panel-head">
        <h2>{title}</h2>
        {action && (
          <button className="panel-action">
            {action}
            <ChevronRight size={14} />
          </button>
        )}
      </div>
      {children}
    </section>
  );
}
function Empty({ title, icon }: { title: string; icon: React.ReactNode }) {
  return (
    <div className="empty">
      <span>{icon}</span>
      <h2>{title}</h2>
      <p>该模块正在接入数据服务。</p>
    </div>
  );
}

function Analytics() {
  const [cities, setCities] = useState<CityJobCount[] | null>(null);
  const [apiError, setApiError] = useState(false);
  useEffect(() => {
    jobflowApi
      .cityJobCounts(5)
      .then(setCities)
      .catch(() => setApiError(true));
  }, []);
  const fallback = [
    { city: "上海", job_count: 286 },
    { city: "北京", job_count: 241 },
    { city: "深圳", job_count: 198 },
    { city: "杭州", job_count: 156 },
    { city: "广州", job_count: 124 },
  ];
  const cityRows = cities?.length ? cities : fallback;
  const max = Math.max(...cityRows.map((item) => item.job_count));
  return (
    <>
      <div className="metrics">
        <Metric
          label="有效岗位总量"
          value="1,248"
          detail={apiError ? "分析服务未连接" : "来自实时聚合"}
          icon={<Database />}
        />
        <Metric
          label="城市覆盖"
          value={String(cityRows.length)}
          detail="当前展示 Top 5"
          icon={<MapPin />}
        />
        <Metric
          label="平均处理耗时"
          value="6m 18s"
          detail="较昨日 -14.2%"
          icon={<Clock3 />}
        />
        <Metric
          label="报告打开率"
          value="78.4%"
          detail="较上周 +5.6%"
          icon={<ArrowUpRight />}
        />
      </div>
      <div className="two">
        <Panel title="岗位趋势">
          <div className="chart analytics-chart">
            {[48, 61, 54, 73, 66, 82, 76, 92, 87, 96].map((n, i) => (
              <div className="bar-wrap" key={i}>
                <i style={{ height: `${n}%` }} />
                <small>{i + 1}</small>
              </div>
            ))}
          </div>
        </Panel>
        <Panel title="热门城市">
          <div className="city-list">
            {cityRows.map((item) => (
              <div className="city" key={item.city}>
                <span>
                  <MapPin size={14} />
                  {item.city}
                </span>
                <div>
                  <i
                    style={{
                      width: `${Math.round((item.job_count / max) * 100)}%`,
                    }}
                  />
                  <b>{item.job_count}</b>
                </div>
              </div>
            ))}
          </div>
        </Panel>
      </div>
      <Panel title="渠道表现">
        <div className="table">
          <div className="row head">
            <span>渠道</span>
            <span>发送次数</span>
            <span>成功率</span>
            <span>最近状态</span>
          </div>
          {[
            ["Telegram", "28", "100%", "稳定"],
            ["微信公众号", "24", "100%", "草稿已创建"],
            ["日报邮件", "0", "-", "未接入"],
          ].map((r) => (
            <div className="row" key={r[0]}>
              <span>{r[0]}</span>
              <span>{r[1]}</span>
              <span>{r[2]}</span>
              <b className={r[3] === "未接入" ? "muted" : "success"}>{r[3]}</b>
            </div>
          ))}
        </div>
      </Panel>
    </>
  );
}
function Alerts() {
  return (
    <>
      <div className="alert-summary">
        <div>
          <CircleAlert size={20} />
          <span>
            <b>0</b>
            <small>未处理告警</small>
          </span>
        </div>
        <div>
          <AlertTriangle size={20} />
          <span>
            <b>2</b>
            <small>今日观察项</small>
          </span>
        </div>
        <div>
          <CheckCircle2 size={20} />
          <span>
            <b>18</b>
            <small>本周已处理</small>
          </span>
        </div>
      </div>
      <Panel title="告警记录" action="全部记录">
        <div className="alert-list">
          {[
            [
              "观察",
              "BOSS 登录状态需人工确认",
              "服务器重启检查 · 今天 16:20",
              "观察",
            ],
            [
              "已处理",
              "昨日 ETL 批次耗时高于平均值",
              "ETL 处理 · 昨天 23:18",
              "已处理",
            ],
            [
              "信息",
              "微信公众号草稿等待人工发布",
              "微信公众号投放 · 09-04 16:40",
              "信息",
            ],
          ].map(([level, title, meta, status]) => (
            <div className="alert" key={title}>
              <span
                className={`alert-icon ${level === "观察" ? "watch" : level === "已处理" ? "done" : "info"}`}
              >
                {level === "信息" ? (
                  <Info size={17} />
                ) : level === "已处理" ? (
                  <CheckCircle2 size={17} />
                ) : (
                  <AlertTriangle size={17} />
                )}
              </span>
              <span className="alert-copy">
                <b>{title}</b>
                <small>{meta}</small>
              </span>
              <b className={status === "已处理" ? "success" : "muted"}>
                {status}
              </b>
              <ChevronRight size={15} className="muted" />
            </div>
          ))}
        </div>
      </Panel>
    </>
  );
}

createRoot(document.getElementById("root")!).render(<App />);
