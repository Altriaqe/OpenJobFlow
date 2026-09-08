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
  type DeliveryStatus,
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
  const [authenticated, setAuthenticated] = useState(false);
  const [token, setToken] = useState("");
  const [authError, setAuthError] = useState("");
  useEffect(() => { jobflowApi.session().then(() => setAuthenticated(true)).catch(() => undefined); }, []);
  const login = async () => {
    setAuthError("");
    try { await jobflowApi.login(token); setToken(""); setAuthenticated(true); }
    catch { setAuthError("管理员 Token 无效"); }
  };
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
          <div className="user">
            {authenticated ? <button className="icon" title="退出管理员会话" onClick={() => jobflowApi.logout().finally(() => setAuthenticated(false))}><ShieldCheck size={16} /></button> : <input aria-label="管理员 Token" type="password" placeholder="管理员 Token" value={token} onChange={(event) => setToken(event.target.value)} onKeyDown={(event) => { if (event.key === "Enter") void login(); }} />}
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
            <button className="icon" onClick={() => window.location.reload()} title="刷新全部数据">
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
            <span className="time">
              <Clock3 size={15} />
              每 30 秒自动刷新
            </span>
          </div>
          {page === "overview" && <LiveStageOverview />}
          {authError && <div className="notice"><AlertTriangle size={18} /><span>{authError}</span></div>}
          {page === "operations" && <Operations authenticated={authenticated} />}
          {page === "delivery" && <Delivery authenticated={authenticated} />}
          {page === "analytics" && <Analytics />}
          {page === "alerts" && <Alerts />}
        </div>
      </main>
    </div>
  );
}
function LiveRecentRuns({ summary }: { summary: DashboardSummary | null }) {
  const runs = summary?.runs ?? [];
  if (!runs.length) return <div className="row"><span>暂无运行记录</span></div>;
  return <div className="table"><div className="row head"><span>操作</span><span>触发时间</span><span>状态</span></div>{runs.slice(0, 5).map(run => <div className="row" key={run.id}><span>{run.kind === "server_check" ? "服务器重启检查" : "恢复运行"}</span><span>{new Date(run.started_at).toLocaleString("zh-CN")}</span><b className={run.status === "succeeded" ? "success" : "muted"}>{run.status === "succeeded" ? "成功" : run.status}</b></div>)}</div>;
}

function LiveStageOverview() {
  const [summary, setSummary] = useState<DashboardSummary | null>(null);
  const [stageError, setStageError] = useState(false);
  const loadSummary = () => jobflowApi.dashboardSummary().then(setSummary).catch(() => setStageError(true));
  useEffect(() => { loadSummary(); const timer = window.setInterval(loadSummary, 30000); return () => window.clearInterval(timer); }, []);
  const rows = summary?.stages ?? [];
  const accepted = rows.filter(item => item.state === "已验收" || item.state === "已完成").length;
  const metrics = summary?.metrics;
  const channelCount = summary?.channels?.filter(item => item.status === "sent" || item.status === "created").length ?? 0;
  const trend = summary?.trend ?? [];
  const maxTrend = Math.max(...trend.map(item => item.row_count), 1);
  return <><div className="metrics"><Metric label="阶段状态" value={`${accepted}/${rows.length}`} detail={stageError ? "监控服务未连接" : "来自实时检查"} icon={<CheckCircle2/>}/><Metric label="有效岗位总量" value={metrics ? String(metrics.job_count) : "-"} detail={metrics ? `${metrics.city_count} 个城市` : "读取中"} icon={<Database/>}/><Metric label="最近 ETL 批次" value={metrics?.batch_row_count == null ? "-" : String(metrics.batch_row_count)} detail={metrics?.batch_status === "succeeded" ? "执行成功" : metrics?.batch_status ?? "读取中"} icon={<Workflow/>}/><Metric label="渠道投放" value={`${channelCount}/2`} detail="来自渠道记录" icon={<Send/>}/></div><div className="two"><Panel title="每日采集量"><div className="chart">{trend.length ? trend.map(item => <div className="bar-wrap" key={item.id}><i style={{height:`${Math.max(8, Math.round(item.row_count / maxTrend * 100))}%`}}/><small>{item.finished_at ? new Date(item.finished_at).toLocaleDateString("zh-CN", {month:"2-digit", day:"2-digit"}) : "-"}</small></div>) : <div className="empty-chart">暂无采集批次</div>}</div></Panel><Panel title="阶段状态"><div className="stage-list">{rows.slice(0,5).map(item=><div className="stage" key={item.id}><span><i className={`dot ${item.state === "异常" ? "error" : ""}`}/>{item.name}</span><b className={`pill ${item.state === "异常" ? "danger" : ""}`}>{item.state}</b></div>)}</div><button className="link" type="button">查看全部阶段 <ChevronRight size={14}/></button></Panel></div><Panel title="最近运行"><LiveRecentRuns summary={summary}/></Panel></>;
}

function Operations({ authenticated }: { authenticated: boolean }) {
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
  const runChecks = async () => {
    if (!authenticated || !window.confirm("确认执行服务器重启检查？此操作只检查状态，不会投放报告。")) return;
    setLoading(true);
    try { await jobflowApi.runChecks(); }
    catch { setError(true); }
    finally { loadOperations(); }
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
        <button className="primary" onClick={authenticated ? runChecks : undefined} disabled={loading || !authenticated}>
          <RefreshCw size={16} />
          {loading ? "执行中..." : authenticated ? "执行服务器检查" : "登录后执行检查"}
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
function Delivery({ authenticated }: { authenticated: boolean }) {
  const today = new Date().toISOString().slice(0, 10);
  const [date, setDate] = useState(today);
  const [statuses, setStatuses] = useState<DeliveryStatus[]>([]);
  const [loading, setLoading] = useState(false);
  useEffect(() => {
    setLoading(true);
    jobflowApi.deliveryStatuses(date).then(setStatuses).finally(() => setLoading(false));
  }, [date]);
  const statusFor = (channel: string) => statuses.find((item) => item.channel === channel);
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
          date={date}
          maxDate={today}
          onDateChange={setDate}
          status={statusFor("telegram")}
          loading={loading}
          authenticated={authenticated}
          action={() => jobflowApi.sendTelegram(date).then((response) => jobflowApi.deliveryStatuses(date).then(setStatuses).then(() => response))}
        />
        <DeliveryCard
          title="微信公众号草稿"
          text="创建指定日期的公众号草稿，不自动发布。"
          date={date}
          maxDate={today}
          onDateChange={setDate}
          status={statusFor("wechat")}
          loading={loading}
          authenticated={authenticated}
          action={() => jobflowApi.createWechatDraft(date).then((response) => jobflowApi.deliveryStatuses(date).then(setStatuses).then(() => response))}
        />
      </div>
    </>
  );
}
function DeliveryCard({ title, text, date, maxDate, onDateChange, status, loading, authenticated, action }: { title: string; text: string; date: string; maxDate: string; onDateChange: (date: string) => void; status?: DeliveryStatus; loading: boolean; authenticated: boolean; action: () => Promise<unknown> }) {
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [result, setResult] = useState("");
  const execute = () => {
    if (!window.confirm(`确认执行“${title}”，日期：${date}？`)) return;
    setError("");
    setResult("");
    setBusy(true);
    action().then(() => setResult("操作已完成")).catch((reason: Error) => setError(reason.message || "操作失败")).finally(() => setBusy(false));
  };
  return (
    <div className="delivery-card">
      <Send className="delivery-icon" size={20} />
      <div className="card-title">
        <h3>{title}</h3>
        <b className={`pill ${status?.status === "failed" ? "danger" : ""}`}>
          {loading ? "读取中" : status?.status ?? "暂无记录"}
        </b>
      </div>
      <p>{text}</p>
      <div className="controls">
        <input type="date" value={date} max={maxDate} onChange={(event) => onDateChange(event.target.value)} />
        <button className="primary" type="button" disabled={!authenticated || busy} onClick={execute}>
          {busy ? "执行中..." : result || (authenticated ? "确认执行" : "登录后执行")}
        </button>
      </div>
      {error && <small className="error-text">{error}</small>}
      {result && <small className="success-text">{result}</small>}
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
  const [summary, setSummary] = useState<DashboardSummary | null>(null);
  const [apiError, setApiError] = useState(false);
  useEffect(() => {
    const load = () => jobflowApi.dashboardSummary().then(setSummary).catch(() => setApiError(true));
    load();
    const timer = window.setInterval(load, 30000);
    return () => window.clearInterval(timer);
  }, []);
  const cityRows = summary?.city_counts ?? [];
  const max = Math.max(...cityRows.map((item) => item.job_count));
  return (
    <>
      <div className="metrics">
        <Metric
          label="有效岗位总量"
          value={summary ? String(summary.metrics.job_count) : "-"}
          detail={apiError ? "分析服务未连接" : "来自实时聚合"}
          icon={<Database />}
        />
        <Metric
          label="城市覆盖"
          value={summary ? String(summary.metrics.city_count) : "-"}
          detail="当前展示 Top 5"
          icon={<MapPin />}
        />
        <Metric
          label="平均处理耗时"
          value="暂无"
          detail="处理时长指标未接入"
          icon={<Clock3 />}
        />
        <Metric
          label="报告打开率"
          value="暂无"
          detail="打开率指标未接入"
          icon={<ArrowUpRight />}
        />
      </div>
      <div className="two">
        <Panel title="岗位趋势">
          <div className="chart analytics-chart">
            {(summary?.trend ?? []).map((item) => (
              <div className="bar-wrap" key={item.id}>
                <i style={{ height: `${Math.max(8, Math.round((item.row_count / Math.max(...(summary?.trend ?? []).map((entry) => entry.row_count), 1)) * 100))}%` }} />
                <small>{item.finished_at ? new Date(item.finished_at).toLocaleDateString("zh-CN", { month: "2-digit", day: "2-digit" }) : "-"}</small>
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
          {(summary?.channels ?? []).map((channel) => (
            <div className="row" key={channel.channel}>
              <span>{channel.channel === "telegram" ? "Telegram" : "微信公众号"}</span>
              <span>{summary?.delivery_totals.total ?? 0}</span>
              <span>{summary ? `${summary.delivery_totals.total ? Math.round(summary.delivery_totals.successful / summary.delivery_totals.total * 100) : 0}%` : "-"}</span>
              <b className={channel.status === "failed" ? "muted" : "success"}>{channel.status}</b>
            </div>
          ))}
        </div>
      </Panel>
    </>
  );
}
function Alerts() {
  const [summary, setSummary] = useState<DashboardSummary | null>(null);
  useEffect(() => {
    const load = () => jobflowApi.dashboardSummary().then(setSummary).catch(() => undefined);
    load();
    const timer = window.setInterval(load, 30000);
    return () => window.clearInterval(timer);
  }, []);
  const alerts = summary?.alerts ?? [];
  return (
    <>
      <div className="alert-summary">
        <div>
          <CircleAlert size={20} />
          <span>
            <b>{alerts.length}</b>
            <small>未处理告警</small>
          </span>
        </div>
        <div>
          <AlertTriangle size={20} />
          <span>
            <b>{alerts.length}</b>
            <small>今日观察项</small>
          </span>
        </div>
        <div>
          <CheckCircle2 size={20} />
          <span>
            <b>{summary?.runs.filter((run) => run.status === "succeeded").length ?? 0}</b>
            <small>本周已处理</small>
          </span>
        </div>
      </div>
      <Panel title="告警记录" action="全部记录">
        <div className="alert-list">
          {alerts.map(({ level, title, detail }) => (
            <div className="alert" key={title}>
              <span
                className="alert-icon watch"
              >
                <AlertTriangle size={17} />
              </span>
              <span className="alert-copy">
                <b>{title}</b>
                <small>{detail}</small>
              </span>
              <b className="muted">未处理</b>
              <ChevronRight size={15} className="muted" />
            </div>
          ))}
        </div>
        {!alerts.length && <div className="empty-inline">当前没有未处理告警</div>}
      </Panel>
    </>
  );
}

createRoot(document.getElementById("root")!).render(<App />);
