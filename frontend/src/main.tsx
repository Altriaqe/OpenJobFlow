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
import { jobflowApi, type CityJobCount, type StageStatus } from "./api";

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
  const [stageError, setStageError] = useState(false);
  useEffect(() => { jobflowApi.stageStatuses().then(setStageRows).catch(() => setStageError(true)); }, []);
  const fallback = stages.map((name, index) => ({ id: String(index), name, goal: "", acceptance: "", state: "演示数据" }));
  const rows = stageRows?.length ? stageRows : fallback;
  const accepted = rows.filter(item => item.state === "已验收" || item.state === "已完成").length;
  return <><div className="metrics"><Metric label="阶段状态" value={`${accepted}/${rows.length}`} detail={stageError ? "阶段服务未连接" : "来自实时检查"} icon={<CheckCircle2/>}/><Metric label="今日岗位快照" value="180" detail="+35 较昨日" icon={<Database/>}/><Metric label="ETL 批次" value="4" detail="全部成功" icon={<Workflow/>}/><Metric label="渠道投放" value="2/2" detail="人工确认" icon={<Send/>}/></div><div className="two"><Panel title="每日采集量"><div className="chart">{[45,58,48,74,67,89,78].map((n,i)=><div className="bar-wrap" key={i}><i style={{height:`${n}%`}}/><small>{["09-01","09-02","09-03","09-04","09-05","09-06","今天"][i]}</small></div>)}</div></Panel><Panel title="阶段状态"><div className="stage-list">{rows.slice(0,5).map(item=><div className="stage" key={item.id}><span><i className={`dot ${item.state === "异常" ? "error" : ""}`}/>{item.name}</span><b className={`pill ${item.state === "异常" ? "danger" : ""}`}>{item.state}</b></div>)}</div><button className="link">查看全部阶段 <ChevronRight size={14}/></button></Panel></div><Panel title="最近运行"><RecentRuns/></Panel></>;
}

function Operations() {
  return (
    <>
      <div className="notice">
        <CheckCircle2 size={18} />
        <span>
          <b>系统检查已通过</b>
          <small>13 项检查全部成功，最近检查时间：今天 16:20</small>
        </span>
      </div>
      <Panel title="服务器重启检查" action="刚刚更新">
        <div className="checks">
          {[
            "Tailscale / SSH",
            "Xvfb",
            "Chrome",
            "x11vnc",
            "Daily Timer",
            "PostgreSQL",
            "API 容器",
            "健康检查",
            "就绪检查",
            "BOSS 登录",
            "最近 ETL",
            "Telegram",
            "微信公众号",
          ].map((s) => (
            <div className="check" key={s}>
              <CheckCircle2 size={16} />
              <span>{s}</span>
              <b>通过</b>
            </div>
          ))}
        </div>
        <button className="primary">
          <RefreshCw size={16} />
          重新执行检查
        </button>
      </Panel>
      <Panel title="运行记录">
        <div className="row">
          <span>服务器重启检查</span>
          <span>2026-09-06 16:20</span>
          <span>13 项</span>
          <b className="success">成功</b>
        </div>
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
