import React, { useEffect, useRef, useState } from "react";
import { createRoot } from "react-dom/client";
import {
	BrowserRouter,
	Link,
	NavLink,
	Route,
	Routes,
	useNavigate,
	useParams,
} from "react-router-dom";
import {
	QueryClient,
	QueryClientProvider,
	useQuery,
	useQueryClient,
} from "@tanstack/react-query";
import {
	Area,
	AreaChart,
	CartesianGrid,
	ResponsiveContainer,
	Tooltip,
	XAxis,
	YAxis,
} from "recharts";
import {
	Activity,
	ArrowDownToLine,
	ArrowLeft,
	ArrowRight,
	Box,
	Check,
	CheckCircle2,
	ChevronDown,
	ChevronRight,
	Circle,
	Clock3,
	Code2,
	Container,
	Copy,
	ExternalLink,
	FileArchive,
	FolderKanban,
	Github,
	Layers3,
	LayoutDashboard,
	LoaderCircle,
	LogOut,
	Moon,
	MoreHorizontal,
	Play,
	Plus,
	Radio,
	RefreshCw,
	Search,
	Server,
	Settings2,
	ShieldCheck,
	Sun,
	Terminal,
	UploadCloud,
	Workflow,
	X,
	Zap,
	Bell,
	Menu,
} from "lucide-react";
import { api, post, token, stamp, short, type Row } from "./api";
import "./styles.css";

const client = new QueryClient({
	defaultOptions: { queries: { refetchInterval: 4000, retry: 1 } },
});
const terminal = ["SUCCEEDED", "FAILED", "CANCELLED", "TIMED_OUT", "LOST"];
const nav = [
	{ path: "/", label: "Overview", icon: LayoutDashboard },
	{ path: "/projects", label: "Projects", icon: FolderKanban },
	{ path: "/deployments", label: "Deployments", icon: Layers3 },
	{ path: "/jobs", label: "Jobs", icon: Play },
	{ path: "/schedules", label: "Schedules", icon: Clock3 },
	{ path: "/workers", label: "Workers", icon: Server },
	{ path: "/monitoring", label: "Monitoring", icon: Activity },
	{ path: "/alerts", label: "Alerts", icon: Bell },
	{ path: "/settings", label: "Settings", icon: Settings2 },
];
function useData(key: string, path: string) {
	return useQuery<Row>({ queryKey: [key, path], queryFn: () => api(path) });
}
function IconButton({
	children,
	onClick,
	title,
}: {
	children: React.ReactNode;
	onClick: () => void;
	title: string;
}) {
	return (
		<button
			className="icon-button"
			onClick={onClick}
			aria-label={title}
			title={title}
		>
			{children}
		</button>
	);
}
function Badge({ status }: { status: string }) {
	return (
		<span className={`badge ${status.toLowerCase()}`}>
			<span className="status-dot" />
			{status.replaceAll("_", " ").toLowerCase()}
		</span>
	);
}
function ErrorBox({ error }: { error?: unknown }) {
	return error ? (
		<div className="error" role="alert">
			{error instanceof Error ? error.message : String(error)}
		</div>
	) : null;
}
function Empty({
	title,
	text,
	action,
}: {
	title: string;
	text: string;
	action?: React.ReactNode;
}) {
	return (
		<div className="empty">
			<Box size={27} />
			<h3>{title}</h3>
			<p>{text}</p>
			{action}
		</div>
	);
}
function Heading({
	eyebrow,
	title,
	description,
	actions,
}: {
	eyebrow?: string;
	title: string;
	description: string;
	actions?: React.ReactNode;
}) {
	return (
		<div className="page-heading">
			<div>
				{eyebrow && <div className="eyebrow">{eyebrow}</div>}
				<h1>{title}</h1>
				<p>{description}</p>
			</div>
			<div className="actions">{actions}</div>
		</div>
	);
}
function Panel({
	title,
	subtitle,
	aside,
	children,
	className = "",
}: {
	title: string;
	subtitle?: string;
	aside?: React.ReactNode;
	children: React.ReactNode;
	className?: string;
}) {
	return (
		<section className={`panel ${className}`}>
			<div className="panel-heading">
				<div>
					<h2>{title}</h2>
					{subtitle && <p>{subtitle}</p>}
				</div>
				{aside}
			</div>
			{children}
		</section>
	);
}
function Modal({
	title,
	children,
	close,
	wide = false,
}: {
	title: string;
	children: React.ReactNode;
	close: () => void;
	wide?: boolean;
}) {
	useEffect(() => {
		const h = (e: KeyboardEvent) => {
			if (e.key === "Escape") close();
		};
		window.addEventListener("keydown", h);
		return () => window.removeEventListener("keydown", h);
	}, [close]);
	return (
		<div
			className="modal-backdrop"
			onMouseDown={(e) => {
				if (e.target === e.currentTarget) close();
			}}
		>
			<div
				className={`modal ${wide ? "wide" : ""}`}
				role="dialog"
				aria-modal="true"
				aria-label={title}
			>
				<header>
					<h2>{title}</h2>
					<IconButton title="Close" onClick={close}>
						<X size={19} />
					</IconButton>
				</header>
				{children}
			</div>
		</div>
	);
}
function Field({
	label,
	children,
	hint,
}: {
	label: string;
	children: React.ReactNode;
	hint?: string;
}) {
	return (
		<label className="field">
			<span>{label}</span>
			{children}
			{hint && <small>{hint}</small>}
		</label>
	);
}
function FormAction({ busy, label }: { busy: boolean; label: string }) {
	return (
		<button className="button primary" disabled={busy} type="submit">
			{busy ? (
				<LoaderCircle className="spin" size={15} />
			) : (
				<ArrowRight size={15} />
			)}{" "}
			{label}
		</button>
	);
}

export function Login({ done }: { done: () => void }) {
	const [error, setError] = useState<unknown>();
	const [busy, setBusy] = useState(false);
	return (
		<div className="login-page">
			<div className="login-brand">
				<Workflow size={30} />
				<span>CrawlOps</span>
			</div>
			<div className="login-card">
				<div className="eyebrow">YOUR CRAWL CONTROL PLANE</div>
				<h1>Welcome back.</h1>
				<p>Sign in to manage your Scrapy infrastructure.</p>
				<form
					onSubmit={async (e) => {
						e.preventDefault();
						setBusy(true);
						setError(undefined);
						const f = new FormData(e.currentTarget);
						try {
							const result = await post("/auth/login", {
								email: f.get("email"),
								password: f.get("password"),
							});
							sessionStorage.setItem("crawlops-token", result.token);
							done();
						} catch (err) {
							setError(err);
						} finally {
							setBusy(false);
						}
					}}
				>
					<Field label="Email">
						<input
							name="email"
							type="email"
							defaultValue="admin@crawlops.local"
							autoComplete="username"
							required
						/>
					</Field>
					<Field label="Password">
						<input
							name="password"
							type="password"
							autoComplete="current-password"
							required
						/>
					</Field>
					<ErrorBox error={error} />
					<FormAction busy={busy} label="Sign in" />
				</form>
			</div>
			<p className="login-footer">
				<ShieldCheck size={14} /> Self-hosted. Your infrastructure. Your data.
			</p>
		</div>
	);
}
export function App() {
	const [authed, setAuthed] = useState(!!token());
	const [theme, setTheme] = useState(
		localStorage.getItem("crawlops-theme") || "dark",
	);
	const [mobile, setMobile] = useState(false);
	useEffect(() => {
		document.documentElement.dataset.theme = theme;
		localStorage.setItem("crawlops-theme", theme);
	}, [theme]);
	useEffect(() => {
		const h = () => setAuthed(!!token());
		window.addEventListener("auth-change", h);
		return () => window.removeEventListener("auth-change", h);
	}, []);
	const account = useQuery<Row>({
		queryKey: ["user"],
		queryFn: () => api("/auth/me"),
		enabled: authed,
	});
	if (!authed)
		return (
			<Login
				done={() => {
					client.clear();
					setAuthed(true);
				}}
			/>
		);
	return (
		<div className="app-shell">
			<aside className={`sidebar ${mobile ? "open" : ""}`}>
				<Link to="/" className="brand">
					<div className="brand-mark">
						<Workflow size={23} />
					</div>
					CrawlOps<span className="version">BETA</span>
				</Link>
				<div className="workspace">
					<span className="workspace-icon">C</span>
					<div>
						<strong>Default workspace</strong>
						<small>Self-hosted instance</small>
					</div>
					<ChevronDown size={14} />
				</div>
				<span className="nav-label">WORKSPACE</span>
				<nav>
					{nav.map((n, i) => (
						<React.Fragment key={n.path}>
							{i === 6 && (
								<span className="nav-label operations">OPERATIONS</span>
							)}
							<NavLink
								to={n.path}
								end={n.path === "/"}
								onClick={() => setMobile(false)}
								className={({ isActive }) =>
									isActive ? "nav-link active" : "nav-link"
								}
							>
								<n.icon size={17} />
								<span>{n.label}</span>
								{n.path === "/jobs" && <span className="nav-hint">↵</span>}
							</NavLink>
						</React.Fragment>
					))}
				</nav>
				<div className="sidebar-bottom">
					<div className="engine-note">
						<span className="status-dot" />
						<span>Container-native execution</span>
					</div>
					<a
						className="docs-link"
						href="/docs"
						target="_blank"
						rel="noreferrer"
					>
						<Code2 size={16} /> API reference <ExternalLink size={12} />
					</a>
					<div className="profile">
						<span className="avatar">AD</span>
						<div>
							<strong>{account.data?.email || "Account"}</strong>
							<small>{account.data?.role || "Default workspace"}</small>
						</div>
						<IconButton
							title="Sign out"
							onClick={() => {
								void post("/auth/logout").catch(() => {});
								sessionStorage.removeItem("crawlops-token");
								client.clear();
								setAuthed(false);
							}}
						>
							<LogOut size={15} />
						</IconButton>
					</div>
				</div>
			</aside>
			<div className="main-shell">
				<header className="topbar">
					<div className="breadcrumb">
						<IconButton
							title="Toggle navigation"
							onClick={() => setMobile(!mobile)}
						>
							<Menu size={17} />
						</IconButton>
						<span>Workspace</span>
						<ChevronRight size={13} />
						<strong>CrawlOps</strong>
					</div>
					<div className="topbar-right">
						<span className="private-label">
							<ShieldCheck size={13} /> Private infrastructure
						</span>
						<span className="top-separator" />
						<IconButton
							title="Toggle theme"
							onClick={() => setTheme(theme === "dark" ? "light" : "dark")}
						>
							{theme === "dark" ? <Sun size={17} /> : <Moon size={17} />}
						</IconButton>
						<Link to="/settings" className="top-avatar" aria-label="Settings">
							AD
						</Link>
					</div>
				</header>
				<main>
					<Routes>
						<Route path="/" element={<Overview />} />
						<Route path="/projects" element={<Projects />} />
						<Route path="/projects/:id" element={<ProjectDetail />} />
						<Route path="/deployments" element={<Deployments />} />
						<Route path="/deployments/:id" element={<DeploymentDetail />} />
						<Route path="/jobs" element={<Jobs />} />
						<Route path="/jobs/:id" element={<JobDetail />} />
						<Route path="/schedules" element={<Schedules />} />
						<Route path="/workers" element={<Workers />} />
						<Route path="/monitoring" element={<Monitoring />} />
						<Route path="/alerts" element={<Alerts />} />
						<Route path="/settings" element={<Settings />} />
						<Route
							path="*"
							element={
								<Empty
									title="Page not found"
									text="Return to your workspace overview."
									action={
										<Link to="/" className="button">
											Go to overview
										</Link>
									}
								/>
							}
						/>
					</Routes>
				</main>
				<footer className="app-footer">
					<span>
						CrawlOps <span className="muted">/</span> Container-native Scrapy
						operations
					</span>
					<span>
						v0.1.0 <span className="footer-dot">•</span> Self-hosted
					</span>
				</footer>
			</div>
		</div>
	);
}
function Overview() {
	const { data, error, isLoading } = useData("overview", "/overview");
	const projects = useData("projects", "/projects");
	const jobs = useData("jobs", "/jobs?limit=200");
	const [deploy, setDeploy] = useState(false);
	const [run, setRun] = useState(false);
	const counts = data?.jobs || {};
	const active =
		(counts.RUNNING || 0) + (counts.STARTING || 0) + (counts.DISPATCHING || 0);
	const completed = counts.SUCCEEDED || 0;
	const failed =
		(counts.FAILED || 0) + (counts.TIMED_OUT || 0) + (counts.LOST || 0);
	const total = Object.values(counts).reduce(
		(a: number, b) => a + Number(b),
		0,
	);
	const chart = Array.from({ length: 7 }, (_, i) => {
		const day = new Date();
		day.setDate(day.getDate() - 6 + i);
		const items = (jobs.data?.items || []).filter(
			(j: Row) => new Date(j.created_at).toDateString() === day.toDateString(),
		);
		return {
			day: day.toLocaleDateString([], { weekday: "short" }),
			succeeded: items.filter((j: Row) => j.status === "SUCCEEDED").length,
			failed: items.filter((j: Row) =>
				["FAILED", "TIMED_OUT", "LOST"].includes(j.status),
			).length,
		};
	});
	return (
		<>
			<Heading
				eyebrow="CONTROL PLANE"
				title="Overview"
				description="Your crawlers, containers, and operations. All in one place."
				actions={
					<>
						<button className="button" onClick={() => setRun(true)}>
							<Play size={15} /> Run spider
						</button>
						<button className="button primary" onClick={() => setDeploy(true)}>
							<Plus size={16} /> Deploy project
						</button>
					</>
				}
			/>
			<ErrorBox error={error} />
			<div className="status-banner">
				<div className="status-banner-icon">
					<Radio size={17} />
				</div>
				<div>
					<strong>
						{isLoading
							? "Connecting to your control plane"
							: data?.workers
								? "Your execution plane is connected"
								: "Your workspace is ready"}
					</strong>
					<span>
						{data?.workers
							? `${data.workers} execution host${data.workers === 1 ? "" : "s"} online and ready to accept jobs.`
							: "Deploy a project and connect an execution worker to start crawling."}
					</span>
				</div>
				<Link to="/workers">
					View workers <ArrowRight size={14} />
				</Link>
			</div>
			<div className="metric-grid">
				{[
					{
						label: "Total projects",
						value: data?.projects,
						icon: FolderKanban,
						sub: `${data?.deployments || 0} ready deployments`,
						color: "purple",
					},
					{
						label: "Running jobs",
						value: active,
						icon: Activity,
						sub: `${counts.QUEUED || 0} jobs in queue`,
						color: "blue",
					},
					{
						label: "Completed jobs",
						value: completed,
						icon: CheckCircle2,
						sub: total
							? `${Math.round((completed / total) * 100)}% of all executions`
							: "No executions yet",
						color: "green",
					},
					{
						label: "Failed jobs",
						value: failed,
						icon: Circle,
						sub: "Failed, timed out, or lost",
						color: "orange",
					},
				].map((m) => (
					<div className="metric-card" key={m.label}>
						<div className="metric-top">
							<span>{m.label}</span>
							<span className={`metric-icon ${m.color}`}>
								<m.icon size={16} />
							</span>
						</div>
						<strong className="metric-number">
							{isLoading ? "—" : (m.value ?? 0)}
						</strong>
						<div className="metric-bottom">
							<span className={`tiny-dot ${m.color}`} />
							{m.sub}
						</div>
					</div>
				))}
			</div>
			<div className="dashboard-middle">
				<Panel
					title="Execution activity"
					subtitle="Completed and failed executions over the last 7 days"
					aside={
						<span className="period-chip">
							<Clock3 size={13} /> Last 7 days
						</span>
					}
				>
					<div className="chart-key">
						<span>
							<i className="legend green" />
							Succeeded
						</span>
						<span>
							<i className="legend orange" />
							Failed
						</span>
						<span className="chart-scope">Latest 200 executions</span>
					</div>
					<div className="chart">
						<ResponsiveContainer width="100%" height="100%">
							<AreaChart
								data={chart}
								margin={{ left: -25, right: 16, top: 10, bottom: 0 }}
							>
								<defs>
									<linearGradient id="success-fill" x1="0" y1="0" x2="0" y2="1">
										<stop offset="0%" stopColor="#41c6a0" stopOpacity={0.25} />
										<stop offset="100%" stopColor="#41c6a0" stopOpacity={0} />
									</linearGradient>
								</defs>
								<CartesianGrid
									stroke="var(--border)"
									strokeDasharray="3 5"
									vertical={false}
								/>
								<XAxis
									dataKey="day"
									tick={{ fill: "var(--muted)", fontSize: 11 }}
									axisLine={false}
									tickLine={false}
								/>
								<YAxis
									allowDecimals={false}
									tick={{ fill: "var(--muted)", fontSize: 11 }}
									axisLine={false}
									tickLine={false}
								/>
								<Tooltip
									contentStyle={{
										background: "var(--panel)",
										border: "1px solid var(--border)",
										borderRadius: 8,
										color: "var(--text)",
									}}
								/>
								<Area
									type="monotone"
									dataKey="succeeded"
									stroke="#41c6a0"
									fill="url(#success-fill)"
									strokeWidth={2}
								/>
								<Area
									type="monotone"
									dataKey="failed"
									stroke="#eaa36b"
									fill="transparent"
									strokeWidth={2}
								/>
							</AreaChart>
						</ResponsiveContainer>
					</div>
				</Panel>
				<Panel
					title="Execution plane"
					subtitle="Infrastructure at a glance"
					aside={<Server size={17} className="muted" />}
				>
					<div className="plane-visual">
						<div className="plane-core">
							<Container size={28} />
						</div>
						<span className="plane-line" />
						<div className="plane-host">
							<Server size={22} />
						</div>
						<span className="plane-line" />
						<div className="plane-host">
							<Box size={22} />
						</div>
					</div>
					<div className="plane-row">
						<span>Available workers</span>
						<strong>
							<i className={`tiny-dot ${data?.workers ? "green" : "orange"}`} />
							{data?.workers || 0} online
						</strong>
					</div>
					<div className="plane-row">
						<span>Execution mode</span>
						<strong>Isolated containers</strong>
					</div>
					<div className="plane-row">
						<span>Deployment artifacts</span>
						<strong>Immutable images</strong>
					</div>
					<Link to="/workers" className="panel-bottom-link">
						Manage infrastructure <ArrowRight size={14} />
					</Link>
				</Panel>
			</div>
			<Panel
				title="Recent executions"
				subtitle="The latest activity across your projects"
				aside={
					<Link className="text-link" to="/jobs">
						View all jobs <ArrowRight size={14} />
					</Link>
				}
			>
				<JobTable
					jobs={data?.recent_jobs || []}
					projects={projects.data?.items || []}
				/>
			</Panel>
			<div className="dashboard-bottom">
				<Panel
					title="Workspace activity"
					aside={<Activity size={16} className="muted" />}
				>
					{data?.activity?.length ? (
						<div className="activity-list">
							{data.activity.slice(0, 5).map((a: Row) => (
								<div className="activity-row" key={a.id}>
									<div className="activity-icon">
										<Layers3 size={15} />
									</div>
									<div>
										<strong>{a.action.replaceAll(".", " ")}</strong>
										<span>{a.actor}</span>
									</div>
									<time>{stamp(a.created_at)}</time>
								</div>
							))}
						</div>
					) : (
						<div className="quiet-empty">
							<Clock3 size={20} />
							<p>Your workspace activity will appear here.</p>
						</div>
					)}
				</Panel>
				<div className="getting-started">
					<div className="getting-icon">
						<Terminal size={22} />
					</div>
					<span className="eyebrow">BUILT FOR YOUR WORKFLOW</span>
					<h2>
						From source to spider.
						<br />
						Without the busywork.
					</h2>
					<p>
						Upload your Scrapy project or bring an existing image. CrawlOps
						handles the rest.
					</p>
					<button className="button" onClick={() => setDeploy(true)}>
						Create a deployment <ArrowRight size={14} />
					</button>
					<span className="decor-brackets">{"{ }"}</span>
				</div>
			</div>
			{deploy && <DeploymentWizard close={() => setDeploy(false)} />}{" "}
			{run && <RunDialog close={() => setRun(false)} />}
		</>
	);
}
function ProjectForm({
	close,
	existing,
}: {
	close: () => void;
	existing?: Row;
}) {
	const qc = useQueryClient();
	const [busy, setBusy] = useState(false);
	const [error, setError] = useState<unknown>();
	return (
		<Modal title={existing ? "Edit project" : "Create a project"} close={close}>
			<form
				onSubmit={async (e) => {
					e.preventDefault();
					const f = new FormData(e.currentTarget);
					setBusy(true);
					try {
						await api(existing ? `/projects/${existing.id}` : "/projects", {
							method: existing ? "PATCH" : "POST",
							body: JSON.stringify({
								name: f.get("name"),
								description: f.get("description"),
							}),
						});
						await qc.invalidateQueries();
						close();
					} catch (err) {
						setError(err);
					} finally {
						setBusy(false);
					}
				}}
			>
				<p className="form-intro">
					A project groups your deployments, spiders, and execution history.
				</p>
				<Field label="Project name">
					<input
						name="name"
						placeholder="e.g. product-catalog"
						pattern="[a-zA-Z0-9][a-zA-Z0-9_.\-]*"
						required
						maxLength={80}
						defaultValue={existing?.name}
					/>
				</Field>
				<Field label="Description">
					<textarea
						name="description"
						rows={3}
						placeholder="What does this project crawl?"
						defaultValue={existing?.description}
					/>
				</Field>
				<ErrorBox error={error} />
				<div className="form-footer">
					<button type="button" className="button" onClick={close}>
						Cancel
					</button>
					<FormAction
						busy={busy}
						label={existing ? "Save changes" : "Create project"}
					/>
				</div>
			</form>
		</Modal>
	);
}
export function Projects() {
	const { data, error, isLoading } = useData("projects", "/projects");
	const deps = useData("deployments", "/deployments?limit=200");
	const [create, setCreate] = useState(false);
	const [search, setSearch] = useState("");
	const items = (data?.items || []).filter((p: Row) =>
		p.name.toLowerCase().includes(search.toLowerCase()),
	);
	return (
		<>
			<Heading
				eyebrow="WORKSPACE"
				title="Projects"
				description="Isolated environments for every Scrapy application."
				actions={
					<button className="button primary" onClick={() => setCreate(true)}>
						<Plus size={16} /> Create project
					</button>
				}
			/>
			<ErrorBox error={error} />
			<div className="list-toolbar">
				<div className="search-input">
					<Search size={16} />
					<input
						aria-label="Search projects"
						placeholder="Search projects…"
						value={search}
						onChange={(e) => setSearch(e.target.value)}
					/>
				</div>
				<span className="muted">{data?.total || 0} projects</span>
			</div>
			{items.length ? (
				<div className="project-grid">
					{items.map((p: Row) => (
						<Link className="project-card" to={`/projects/${p.id}`} key={p.id}>
							<div className="project-card-top">
								<div className="project-mark">
									<FolderKanban size={22} />
								</div>
								<span className="project-arrow">
									<ArrowRight size={17} />
								</span>
							</div>
							<h2>{p.name}</h2>
							<p>{p.description || "No description provided."}</p>
							<div className="project-card-bottom">
								<span>
									<Layers3 size={14} />
									{
										(deps.data?.items || []).filter(
											(d: Row) => d.project_id === p.id,
										).length
									}{" "}
									deployments
								</span>
								<span
									className={p.active_deployment_id ? "green-text" : "muted"}
								>
									{p.active_deployment_id ? "Active" : "Undeployed"}
								</span>
							</div>
						</Link>
					))}
				</div>
			) : (
				<Empty
					title={isLoading ? "Loading projects…" : "A home for your crawlers"}
					text="Create your first project, then deploy an archive or Docker image."
					action={
						<button className="button primary" onClick={() => setCreate(true)}>
							<Plus size={15} /> Create project
						</button>
					}
				/>
			)}{" "}
			{create && <ProjectForm close={() => setCreate(false)} />}
		</>
	);
}
function ProjectDetail() {
	const { id } = useParams();
	const { data: project, error } = useData("project", `/projects/${id}`);
	const deps = useData("deployments", `/deployments?project_id=${id}`);
	const jobs = useData("jobs", `/jobs?project_id=${id}`);
	const [deploy, setDeploy] = useState(false);
	const [run, setRun] = useState(false);
	const [edit, setEdit] = useState(false);
	return (
		<>
			<Link className="back-link" to="/projects">
				<ArrowLeft size={14} /> All projects
			</Link>
			<Heading
				eyebrow="SCRAPY PROJECT"
				title={project?.name || "Project"}
				description={
					project?.description ||
					"Deployments and executions for this application."
				}
				actions={
					<>
						<button className="button" onClick={() => setEdit(true)}>
							<Settings2 size={15} /> Edit
						</button>
						<button className="button" onClick={() => setRun(true)}>
							<Play size={15} /> Run spider
						</button>
						<button className="button primary" onClick={() => setDeploy(true)}>
							<Plus size={15} /> Deploy version
						</button>
					</>
				}
			/>
			<ErrorBox error={error} />
			<Panel
				title="Deployment history"
				subtitle="Every execution is pinned to an immutable image."
			>
				<DeploymentTable
					deployments={deps.data?.items || []}
					active={project?.active_deployment_id}
				/>
			</Panel>
			<div className="section-gap" />
			<Panel title="Recent executions">
				<JobTable
					jobs={jobs.data?.items || []}
					projects={project ? [project] : []}
				/>
			</Panel>
			{deploy && (
				<DeploymentWizard projectId={id} close={() => setDeploy(false)} />
			)}{" "}
			{run && <RunDialog projectId={id} close={() => setRun(false)} />}{" "}
			{edit && project && (
				<ProjectForm existing={project} close={() => setEdit(false)} />
			)}
		</>
	);
}
function DeploymentTable({
	deployments,
	active,
}: {
	deployments: Row[];
	active?: string;
}) {
	return deployments.length ? (
		<div className="table-scroll">
			<table>
				<thead>
					<tr>
						<th>Deployment</th>
						<th>Source</th>
						<th>Status</th>
						<th>Created</th>
						<th />
					</tr>
				</thead>
				<tbody>
					{deployments.map((d) => (
						<tr key={d.id}>
							<td>
								<Link className="table-primary" to={`/deployments/${d.id}`}>
									<Layers3 size={15} />
									{d.version}
									{active === d.id && (
										<span className="active-label">active</span>
									)}
								</Link>
								<span className="table-secondary mono">{short(d.id)}</span>
							</td>
							<td>
								<span className="source-label">
									{d.source === "archive" ? (
										<FileArchive size={14} />
									) : (
										<Container size={14} />
									)}{" "}
									{d.source}
								</span>
							</td>
							<td>
								<Badge status={d.status} />
							</td>
							<td className="muted">{stamp(d.created_at)}</td>
							<td>
								<Link
									to={`/deployments/${d.id}`}
									aria-label={`View ${d.version}`}
								>
									<ChevronRight size={16} />
								</Link>
							</td>
						</tr>
					))}
				</tbody>
			</table>
		</div>
	) : (
		<Empty
			title="No deployments yet"
			text="Upload a Scrapy project archive or register a container image."
		/>
	);
}
function Deployments() {
	const { data, error } = useData("deployments", "/deployments");
	const [open, setOpen] = useState(false);
	return (
		<>
			<Heading
				eyebrow="DELIVERY"
				title="Deployments"
				description="Versioned, reproducible environments for your spiders."
				actions={
					<button className="button primary" onClick={() => setOpen(true)}>
						<Plus size={16} /> New deployment
					</button>
				}
			/>
			<ErrorBox error={error} />
			<Panel
				title="All deployments"
				aside={<span className="count-label">{data?.total || 0} total</span>}
			>
				<DeploymentTable deployments={data?.items || []} />
			</Panel>
			{open && <DeploymentWizard close={() => setOpen(false)} />}
		</>
	);
}
export function DeploymentWizard({
	close,
	projectId,
}: {
	close: () => void;
	projectId?: string;
}) {
	const navigate = useNavigate();
	const qc = useQueryClient();
	const projects = useData("projects", "/projects");
	const [source, setSource] = useState("archive");
	const [step, setStep] = useState(1);
	const [project, setProject] = useState(projectId || "");
	const [file, setFile] = useState<File>();
	const [version, setVersion] = useState(
		`v${new Date().toISOString().replace(/[:.]/g, "-").slice(0, 19)}`,
	);
	const [reference, setReference] = useState("");
	const [python, setPython] = useState("3.12");
	const [buildArgs, setBuildArgs] = useState("{}");
	const [busy, setBusy] = useState(false);
	const [error, setError] = useState<unknown>();
	return (
		<Modal title="Create a deployment" close={close} wide>
			<div className="wizard-steps">
				{["Source", "Configure", "Build & discover"].map((s, i) => (
					<span key={s} className={step >= i + 1 ? "current" : ""}>
						<i>{step > i + 1 ? <Check size={12} /> : i + 1}</i>
						{s}
						{i < 2 && <ChevronRight size={14} />}
					</span>
				))}
			</div>
			<form
				onSubmit={async (e) => {
					e.preventDefault();
					if (step === 1) {
						setStep(2);
						return;
					}
					setBusy(true);
					setError(undefined);
					try {
						const selected = project || projects.data?.items?.[0]?.id;
						if (!selected)
							throw new Error("Create a project before deploying.");
						let result;
						if (source === "archive" || source === "image_archive") {
							if (!file) throw new Error("Select a ZIP or TAR archive.");
							const args = JSON.parse(buildArgs);
							const f = new FormData();
							f.set("file", file);
							f.set("version", version);
							f.set("options", JSON.stringify({ python, build_args: args }));
							result = await api(
								`/projects/${selected}/deployments/${source === "image_archive" ? "image-archive" : "archive"}`,
								{ method: "POST", body: f },
							);
						} else {
							result = await post(`/projects/${selected}/deployments/image`, {
								reference,
								version,
							});
						}
						await qc.invalidateQueries();
						close();
						navigate(`/deployments/${result.id}`);
					} catch (err) {
						setError(err);
					} finally {
						setBusy(false);
					}
				}}
			>
				{step === 1 ? (
					<>
						<p className="form-intro">
							Choose how to bring your Scrapy project to CrawlOps.
						</p>
						<div className="source-choices">
							<button
								type="button"
								className={`source-choice ${source === "archive" ? "selected" : ""}`}
								onClick={() => setSource("archive")}
							>
								<FileArchive size={26} />
								<strong>Project archive</strong>
								<span>Upload source. We build the image.</span>
								<small>ZIP, TAR, TAR.GZ</small>
								{source === "archive" && (
									<CheckCircle2 size={17} className="choice-check" />
								)}
							</button>
							<button
								type="button"
								className={`source-choice ${source === "image" ? "selected" : ""}`}
								onClick={() => setSource("image")}
							>
								<Container size={26} />
								<strong>Docker image</strong>
								<span>Deploy an existing OCI image.</span>
								<small>Local or registry image</small>
								{source === "image" && (
									<CheckCircle2 size={17} className="choice-check" />
								)}
							</button>
						</div>
						<button
							className="offline-choice"
							type="button"
							onClick={() =>
								setSource(
									source === "image_archive" ? "archive" : "image_archive",
								)
							}
						>
							<ArrowDownToLine size={14} />
							{source === "image_archive"
								? "Offline image import selected ✓"
								: "Air-gapped? Import a Docker image archive"}
						</button>
						<div className="info-note">
							<ShieldCheck size={17} />
							<span>
								Each deployment is pinned to an immutable image. Your project
								dependencies stay isolated.
							</span>
						</div>
					</>
				) : (
					<>
						<div className="form-grid">
							<Field label="Project">
								<select
									value={project || projects.data?.items?.[0]?.id || ""}
									onChange={(e) => setProject(e.target.value)}
									required
								>
									<option value="" disabled>
										Select project
									</option>
									{projects.data?.items?.map((p: Row) => (
										<option key={p.id} value={p.id}>
											{p.name}
										</option>
									))}
								</select>
							</Field>
							<Field label="Version">
								<input
									value={version}
									onChange={(e) => setVersion(e.target.value)}
									required
									maxLength={100}
								/>
							</Field>
						</div>
						{source === "archive" || source === "image_archive" ? (
							<>
								<label className="upload-zone">
									<UploadCloud size={30} />
									<strong>
										{file?.name ||
											(source === "image_archive"
												? "Select a Docker save archive"
												: "Select your Scrapy project archive")}
									</strong>
									<span>
										{file
											? `${(file.size / 1024).toFixed(0)} KB · Ready to upload`
											: source === "image_archive"
												? "Uncompressed docker save TAR · Up to 512 MB"
												: "ZIP or TAR containing scrapy.cfg · Up to 50 MB"}
									</span>
									<input
										aria-label="Project archive"
										type="file"
										accept={
											source === "image_archive" ? ".tar" : ".zip,.tar,.gz,.tgz"
										}
										required
										onChange={(e) => setFile(e.target.files?.[0])}
									/>
								</label>
								<div className="form-grid">
									<Field label="Python version">
										<select
											value={python}
											onChange={(e) => setPython(e.target.value)}
										>
											<option>3.12</option>
											<option>3.13</option>
										</select>
									</Field>
									<Field
										label="Build arguments (JSON)"
										hint="PIP_INDEX_URL, HTTP_PROXY, HTTPS_PROXY, NO_PROXY"
									>
										<input
											className="mono"
											value={buildArgs}
											onChange={(e) => setBuildArgs(e.target.value)}
										/>
									</Field>
								</div>
							</>
						) : (
							<Field
								label="Image reference"
								hint="The builder resolves this image, validates Scrapy, and discovers spiders."
							>
								<input
									placeholder="registry.internal/team/crawler:1.2"
									value={reference}
									onChange={(e) => setReference(e.target.value)}
									required
								/>
							</Field>
						)}
						<div className="info-note">
							<Terminal size={17} />
							<span>
								Follow build logs and spider discovery on the next screen.
								Activate the deployment when validation completes.
							</span>
						</div>
					</>
				)}
				<ErrorBox error={error} />
				<div className="form-footer">
					<button
						className="button"
						type="button"
						onClick={step === 1 ? close : () => setStep(1)}
					>
						{step === 1 ? "Cancel" : "Back"}
					</button>
					<FormAction
						busy={busy}
						label={
							step === 1
								? "Continue"
								: source === "archive"
									? "Build deployment"
									: "Validate image"
						}
					/>
				</div>
			</form>
		</Modal>
	);
}
export function LogViewer({ kind, id }: { kind: string; id: string }) {
	const [chunks, setChunks] = useState<Row[]>([]);
	const [paused, setPaused] = useState(false);
	const [search, setSearch] = useState("");
	const [level, setLevel] = useState("ALL");
	const [error, setError] = useState<unknown>();
	const bottom = useRef<HTMLDivElement>(null);
	const cursor = useRef(-1);
	useEffect(() => {
		setChunks([]);
		cursor.current = -1;
	}, [id]);
	useEffect(() => {
		if (paused) return;
		let cancelled = false;
		const load = async () => {
			try {
				const rows = await api(`/logs/${kind}/${id}?after=${cursor.current}`);
				if (!cancelled && rows.length) {
					cursor.current = rows.at(-1).sequence;
					setChunks((c) => [...c, ...rows].slice(-3000));
				}
				if (!cancelled) setError(undefined);
			} catch (err) {
				if (!cancelled) setError(err);
			}
		};
		void load();
		const timer = setInterval(load, 2000);
		return () => {
			cancelled = true;
			clearInterval(timer);
		};
	}, [kind, id, paused]);
	useEffect(() => {
		if (!paused) bottom.current?.scrollIntoView({ block: "nearest" });
	}, [chunks, paused]);
	const lines = chunks
		.flatMap((c) => c.text.split("\n"))
		.filter(
			(line) =>
				line &&
				line.toLowerCase().includes(search.toLowerCase()) &&
				(level === "ALL" || line.includes(level)),
		);
	return (
		<div className="log-viewer">
			<div className="log-toolbar">
				<span>
					<span className={`tiny-dot ${paused ? "orange" : "green"}`} />
					{paused ? "Paused" : "Live tail"}
				</span>
				<div>
					<div className="log-search">
						<Search size={13} />
						<input
							placeholder="Search logs…"
							aria-label="Search logs"
							value={search}
							onChange={(e) => setSearch(e.target.value)}
						/>
					</div>
					<select
						aria-label="Log level"
						value={level}
						onChange={(e) => setLevel(e.target.value)}
					>
						<option>ALL</option>
						<option>ERROR</option>
						<option>WARNING</option>
						<option>INFO</option>
						<option>DEBUG</option>
					</select>
					<button className="button small" onClick={() => setPaused(!paused)}>
						{paused ? "Resume" : "Pause"}
					</button>
					<IconButton
						title="Download full logs"
						onClick={async () => {
							try {
								const r = await fetch(`/api/logs/${kind}/${id}/download`, {
									headers: { Authorization: `Bearer ${token()}` },
								});
								if (!r.ok) throw new Error("Download failed");
								const url = URL.createObjectURL(await r.blob());
								const a = document.createElement("a");
								a.href = url;
								a.download = `crawlops-${id}.log`;
								a.click();
								URL.revokeObjectURL(url);
							} catch (err) {
								setError(err);
							}
						}}
					>
						<ArrowDownToLine size={15} />
					</IconButton>
				</div>
			</div>
			<ErrorBox error={error} />
			<div className="log-content" role="log" aria-live="off">
				{lines.length ? (
					lines.map((line, i) => (
						<div
							className={`log-line ${line.includes("ERROR") ? "log-error" : line.includes("WARNING") ? "log-warning" : ""}`}
							key={i}
						>
							<span>{i + 1}</span>
							<code>{line}</code>
						</div>
					))
				) : (
					<div className="log-wait">
						<Terminal size={19} /> Waiting for log output…
					</div>
				)}
				<div ref={bottom} />
			</div>
			<div className="log-foot">
				<span>Durable logs · resumes from last received offset</span>
				<span>{lines.length} lines shown</span>
			</div>
		</div>
	);
}
function DeploymentDetail() {
	const { id } = useParams();
	const { data, error } = useData("deployment", `/deployments/${id}`);
	const [actionError, setError] = useState<unknown>();
	const [run, setRun] = useState(false);
	const [activated, setActivated] = useState(false);
	const qc = useQueryClient();
	return (
		<>
			<Link
				className="back-link"
				to={data ? `/projects/${data.project_id}` : "/deployments"}
			>
				<ArrowLeft size={14} /> Back to project
			</Link>
			<Heading
				eyebrow="DEPLOYMENT"
				title={data?.version || "Deployment"}
				description="Build, validate, discover, and activate your project version."
				actions={
					<>
						{data && <Badge status={data.status} />}
						<button
							className="button"
							disabled={data?.status !== "READY"}
							onClick={() => setRun(true)}
						>
							<Play size={15} /> Run spider
						</button>
						<button
							className="button primary"
							disabled={data?.status !== "READY" || activated}
							onClick={async () => {
								try {
									await post(`/deployments/${id}/activate`);
									await qc.invalidateQueries();
									setActivated(true);
								} catch (err) {
									setError(err);
								}
							}}
						>
							<Check size={15} />
							{activated ? "Activated" : "Activate deployment"}
						</button>
					</>
				}
			/>
			<ErrorBox error={error || actionError || data?.error} />
			<div className="deployment-progress">
				{[
					"Received",
					"Build / validate",
					"Discover spiders",
					"Ready to activate",
				].map((s, i) => {
					const stage =
						data?.status === "READY"
							? 4
							: ["BUILDING", "VALIDATING"].includes(data?.status)
								? 2
								: 1;
					return (
						<div key={s} className={i < stage ? "complete" : ""}>
							<span>
								{i < stage && (stage === 4 || i === 0) ? (
									<Check size={16} />
								) : (
									i + 1
								)}
							</span>
							<strong>{s}</strong>
						</div>
					);
				})}
			</div>
			<div className="detail-grid">
				<Panel
					title="Available spiders"
					subtitle="Discovered directly from this image."
				>
					{data?.spiders?.length ? (
						<div className="spider-list">
							{data.spiders.map((s: string) => (
								<div key={s}>
									<span>
										<Code2 size={16} />
										<strong>{s}</strong>
									</span>
									<button className="button small" onClick={() => setRun(true)}>
										<Play size={12} /> Run
									</button>
								</div>
							))}
						</div>
					) : (
						<div className="quiet-empty">
							<Search size={20} />
							<p>Spiders appear when discovery completes.</p>
						</div>
					)}
				</Panel>
				<Panel title="Image artifact">
					<dl className="details-list">
						<div>
							<dt>Source</dt>
							<dd>{data?.source || "—"}</dd>
						</div>
						<div>
							<dt>Image ID</dt>
							<dd className="mono break">
								{data?.artifact?.image_id || "Awaiting validation"}
							</dd>
						</div>
						<div>
							<dt>Registry digest</dt>
							<dd className="mono break">
								{data?.artifact?.digest || "Local content-addressed image"}
							</dd>
						</div>
						<div>
							<dt>Created</dt>
							<dd>{stamp(data?.created_at)}</dd>
						</div>
					</dl>
				</Panel>
			</div>
			<Panel
				title="Build output"
				subtitle="Source validation, image build, and spider discovery logs."
				aside={data?.build && <Badge status={data.build.status} />}
			>
				{data?.build ? (
					<LogViewer kind="build" id={data.build.id} />
				) : (
					<div className="quiet-empty">Loading build…</div>
				)}
			</Panel>
			{run && (
				<RunDialog
					projectId={data?.project_id}
					deploymentId={id}
					close={() => setRun(false)}
				/>
			)}
		</>
	);
}
export function RunDialog({
	close,
	projectId,
	deploymentId,
	schedule = false,
}: {
	close: () => void;
	projectId?: string;
	deploymentId?: string;
	schedule?: boolean;
}) {
	const navigate = useNavigate();
	const qc = useQueryClient();
	const deps = useData(
		"deployments",
		`/deployments?limit=200${projectId ? `&project_id=${projectId}` : ""}`,
	);
	const envs = useData("environments", "/environments");
	const ready = (deps.data?.items || []).filter(
		(d: Row) => d.status === "READY",
	);
	const [dep, setDep] = useState(deploymentId || "");
	const selected = dep || ready[0]?.id || "";
	const detail = useQuery<Row>({
		queryKey: ["deployment", selected],
		queryFn: () => api(`/deployments/${selected}`),
		enabled: !!selected,
	});
	const [spider, setSpider] = useState("");
	const [error, setError] = useState<unknown>();
	const [busy, setBusy] = useState(false);
	const [preview, setPreview] = useState<string[]>([]);
	function spec(form: HTMLFormElement) {
		const f = new FormData(form);
		return {
			deployment_id: selected,
			spider: spider || detail.data?.spiders?.[0],
			arguments: JSON.parse(String(f.get("arguments")) || "{}"),
			settings: JSON.parse(String(f.get("settings")) || "{}"),
			environment_id: f.get("environment") || null,
			timeout: Number(f.get("timeout")),
			memory_mb: Number(f.get("memory")),
			cpu: Number(f.get("cpu")),
			max_retries: Number(f.get("retries")),
			...(schedule
				? {
						name: f.get("name"),
						cron: f.get("cron") || null,
						run_at: f.get("run_at")
							? new Date(String(f.get("run_at"))).toISOString()
							: null,
						timezone: f.get("timezone"),
						overlap: f.get("overlap"),
						misfire: f.get("misfire"),
						max_concurrent: Number(f.get("concurrency")),
					}
				: {}),
		};
	}
	return (
		<Modal
			title={schedule ? "Create a schedule" : "Run a spider"}
			close={close}
			wide
		>
			<form
				onSubmit={async (e) => {
					e.preventDefault();
					setBusy(true);
					setError(undefined);
					try {
						const result = await post(
							schedule ? "/schedules" : "/jobs",
							spec(e.currentTarget),
						);
						await qc.invalidateQueries();
						close();
						navigate(schedule ? "/schedules" : `/jobs/${result.id}`);
					} catch (err) {
						setError(err);
					} finally {
						setBusy(false);
					}
				}}
			>
				<p className="form-intro">
					{schedule
						? "Pin a deployment and configure durable recurring or one-time execution."
						: "Start a disposable container with its own dependencies and resource limits."}
				</p>
				<div className="form-grid">
					<Field label="Deployment version">
						<select
							value={selected}
							required
							onChange={(e) => {
								setDep(e.target.value);
								setSpider("");
							}}
						>
							<option value="" disabled>
								Select a ready deployment
							</option>
							{ready.map((d: Row) => (
								<option key={d.id} value={d.id}>
									{d.version} · {short(d.project_id)}
								</option>
							))}
						</select>
					</Field>
					<Field label="Spider">
						<select
							required
							value={spider || detail.data?.spiders?.[0] || ""}
							onChange={(e) => setSpider(e.target.value)}
						>
							<option value="" disabled>
								Select spider
							</option>
							{detail.data?.spiders?.map((s: string) => (
								<option key={s}>{s}</option>
							))}
						</select>
					</Field>
				</div>
				<div className="form-grid">
					<Field label="Spider arguments (JSON)">
						<textarea
							name="arguments"
							rows={3}
							className="mono"
							defaultValue="{}"
						/>
					</Field>
					<Field
						label="Scrapy settings (JSON)"
						hint="Allowed overrides are validated by the API."
					>
						<textarea
							name="settings"
							rows={3}
							className="mono"
							defaultValue="{}"
						/>
					</Field>
				</div>
				<Field label="Environment">
					<select name="environment">
						<option value="">Default · no extra variables</option>
						{envs.data &&
							Array.isArray(envs.data) &&
							envs.data.map((env: Row) => (
								<option key={env.id} value={env.id}>
									{env.name}
								</option>
							))}
					</select>
				</Field>
				<div className="form-grid four">
					<Field label="Timeout (seconds)">
						<input
							name="timeout"
							type="number"
							min={10}
							max={604800}
							defaultValue={3600}
							required
						/>
					</Field>
					<Field label="Memory (MB)">
						<input
							name="memory"
							type="number"
							min={64}
							max={32768}
							defaultValue={512}
							required
						/>
					</Field>
					<Field label="CPU cores">
						<input
							name="cpu"
							type="number"
							min={0.1}
							max={32}
							step={0.1}
							defaultValue={1}
							required
						/>
					</Field>
					<Field label="Execution retries">
						<input
							name="retries"
							type="number"
							min={0}
							max={5}
							defaultValue={0}
							required
						/>
					</Field>
				</div>
				{schedule && (
					<>
						<div className="form-divider">SCHEDULE CONFIGURATION</div>
						<Field label="Schedule name">
							<input name="name" placeholder="Daily catalog refresh" required />
						</Field>
						<div className="form-grid">
							<Field
								label="Cron expression"
								hint="Five fields: minute hour day month weekday."
							>
								<input name="cron" defaultValue="0 6 * * *" className="mono" />
							</Field>
							<Field label="Time zone">
								<input
									name="timezone"
									defaultValue={
										Intl.DateTimeFormat().resolvedOptions().timeZone
									}
									required
								/>
							</Field>
						</div>
						<Field label="One-time execution (leave cron empty)">
							<input name="run_at" type="datetime-local" />
						</Field>
						<div className="form-grid">
							<Field label="Overlap policy">
								<select name="overlap">
									<option value="forbid">
										Skip while a previous job is active
									</option>
									<option value="allow">Allow overlapping jobs</option>
								</select>
							</Field>
							<Field label="Missed executions">
								<select name="misfire">
									<option value="skip">Skip missed occurrences</option>
									<option value="catch_up">Catch up missed occurrences</option>
								</select>
							</Field>
						</div>
						<Field label="Maximum concurrent jobs">
							<input
								name="concurrency"
								type="number"
								min={1}
								max={100}
								defaultValue={1}
							/>
						</Field>
						<button
							type="button"
							className="button small"
							onClick={async (e) => {
								try {
									const r = await post(
										"/schedules/preview",
										spec(e.currentTarget.form!),
									);
									setPreview(r.next);
								} catch (err) {
									setError(err);
								}
							}}
						>
							<Clock3 size={14} /> Preview next executions
						</button>
						{preview.length > 0 && (
							<div className="preview-times">
								{preview.map((t) => (
									<span key={t}>{new Date(t).toLocaleString()}</span>
								))}
							</div>
						)}
					</>
				)}
				<ErrorBox error={error || detail.error} />
				<div className="form-footer">
					<button className="button" type="button" onClick={close}>
						Cancel
					</button>
					<FormAction
						busy={busy}
						label={schedule ? "Create schedule" : "Start execution"}
					/>
				</div>
			</form>
		</Modal>
	);
}
function JobTable({ jobs, projects = [] }: { jobs: Row[]; projects?: Row[] }) {
	const names = Object.fromEntries(projects.map((p) => [p.id, p.name]));
	return jobs.length ? (
		<div className="table-scroll">
			<table>
				<thead>
					<tr>
						<th>Spider / project</th>
						<th>Status</th>
						<th>Deployment</th>
						<th>Trigger</th>
						<th>Created</th>
						<th />
					</tr>
				</thead>
				<tbody>
					{jobs.map((j) => (
						<tr key={j.id}>
							<td>
								<Link className="table-primary" to={`/jobs/${j.id}`}>
									<span className="spider-cell-icon">
										<Code2 size={15} />
									</span>
									{j.spider}
								</Link>
								<span className="table-secondary">
									{names[j.project_id] || short(j.project_id)}{" "}
									<span className="mono">/ {short(j.id)}</span>
								</span>
							</td>
							<td>
								<Badge status={j.status} />
							</td>
							<td>
								<Link
									className="image-chip mono"
									to={`/deployments/${j.deployment_id}`}
								>
									<Box size={12} />
									{short(j.deployment_id)}
								</Link>
							</td>
							<td>
								<span className="trigger-label">
									{j.trigger === "schedule" ? (
										<Clock3 size={13} />
									) : (
										<Play size={12} />
									)}{" "}
									{j.trigger}
								</span>
							</td>
							<td className="muted">{stamp(j.created_at)}</td>
							<td>
								<Link
									to={`/jobs/${j.id}`}
									aria-label={`View ${j.spider} execution`}
								>
									<ChevronRight size={16} />
								</Link>
							</td>
						</tr>
					))}
				</tbody>
			</table>
		</div>
	) : (
		<Empty
			title="No executions yet"
			text="Run a spider to see live logs, statistics, and execution history here."
		/>
	);
}
function Jobs() {
	const [status, setStatus] = useState("");
	const scheduleFilter = new URLSearchParams(window.location.search).get(
		"schedule",
	);
	const [offset, setOffset] = useState(0);
	const { data, error } = useData(
		"jobs",
		`/jobs?offset=${offset}&limit=25${status ? `&status=${status}` : ""}${scheduleFilter ? `&schedule_id=${scheduleFilter}` : ""}`,
	);
	const projects = useData("projects", "/projects?limit=200");
	const [run, setRun] = useState(false);
	return (
		<>
			<Heading
				eyebrow="EXECUTION"
				title="Jobs"
				description="Every crawl, from first request to final result."
				actions={
					<button className="button primary" onClick={() => setRun(true)}>
						<Play size={15} /> Run spider
					</button>
				}
			/>
			<ErrorBox error={error} />
			<div className="list-toolbar">
				<div className="filter-tabs">
					{[
						["", "All jobs"],
						["RUNNING", "Running"],
						["QUEUED", "Queued"],
						["SUCCEEDED", "Succeeded"],
						["FAILED", "Failed"],
					].map(([v, l]) => (
						<button
							key={v}
							className={status === v ? "selected" : ""}
							onClick={() => {
								setStatus(v);
								setOffset(0);
							}}
						>
							{l}
						</button>
					))}
				</div>
				<span className="muted">{data?.total || 0} executions</span>
			</div>
			<Panel title="Execution history">
				<JobTable
					jobs={data?.items || []}
					projects={projects.data?.items || []}
				/>
			</Panel>
			<div className="pagination">
				<button
					className="button small"
					disabled={!offset}
					onClick={() => setOffset(offset - 25)}
				>
					Previous
				</button>
				<span>Page {offset / 25 + 1}</span>
				<button
					className="button small"
					disabled={offset + 25 >= (data?.total || 0)}
					onClick={() => setOffset(offset + 25)}
				>
					Next
				</button>
			</div>
			{run && <RunDialog close={() => setRun(false)} />}
		</>
	);
}
function JobDetail() {
	const { id } = useParams();
	const { data, error } = useData("job", `/jobs/${id}`);
	const qc = useQueryClient();
	const navigate = useNavigate();
	const [actionError, setError] = useState<unknown>();
	const [attemptIndex, setAttemptIndex] = useState(-1);
	const attempt =
		data?.attempts?.[
			attemptIndex < 0 ? data.attempts.length - 1 : attemptIndex
		];
	const stats = attempt?.statistics || {};
	const [tab, setTab] = useState("logs");
	async function action(a: string) {
		try {
			const result = await post(`/jobs/${id}/${a}`);
			await qc.invalidateQueries();
			if (a === "rerun") navigate(`/jobs/${result.id}`);
		} catch (err) {
			setError(err);
		}
	}
	return (
		<>
			<Link to="/jobs" className="back-link">
				<ArrowLeft size={14} /> All executions
			</Link>
			<Heading
				eyebrow={`EXECUTION / ${short(id)}`}
				title={data?.spider || "Execution"}
				description={`Immutable deployment ${short(data?.deployment_id)} · ${data?.trigger || "manual"} trigger`}
				actions={
					<>
						{data && <Badge status={data.status} />}
						<button
							className="button"
							disabled={!data}
							onClick={() => void action("rerun")}
						>
							<RefreshCw size={15} /> Rerun
						</button>
						{data && !terminal.includes(data.status) && (
							<button
								className="button danger"
								onClick={() => void action("cancel")}
								disabled={data.status === "CANCELLING"}
							>
								<X size={15} /> Cancel job
							</button>
						)}
					</>
				}
			/>
			<ErrorBox error={error || actionError} />
			<div className="metric-grid job-metrics">
				{[
					["Requests", stats["downloader/request_count"] || 0],
					["Items scraped", stats.item_scraped_count || 0],
					["Errors", stats["log_count/ERROR"] || 0],
					["Retries", stats["retry/count"] || 0],
				].map(([label, value]) => (
					<div className="metric-card" key={label}>
						<span className="muted">{label}</span>
						<strong className="metric-number">{value}</strong>
						<span className="metric-bottom">Scrapy statistics</span>
					</div>
				))}
			</div>
			<div className="detail-grid">
				<Panel title="Execution details">
					<dl className="details-list">
						<div>
							<dt>Started</dt>
							<dd>{stamp(attempt?.started_at)}</dd>
						</div>
						<div>
							<dt>Finished</dt>
							<dd>{stamp(attempt?.finished_at)}</dd>
						</div>
						<div>
							<dt>Exit code</dt>
							<dd className="mono">{attempt?.exit_code ?? "—"}</dd>
						</div>
						<div>
							<dt>Container</dt>
							<dd className="mono">
								{attempt?.container_id?.slice(0, 16) || "Awaiting dispatch"}
							</dd>
						</div>
						<div>
							<dt>Worker</dt>
							<dd className="mono">{short(attempt?.host_id)}</dd>
						</div>
						<div>
							<dt>Memory usage</dt>
							<dd>
								{(
									(attempt?.resources?.memory_bytes || 0) /
									1024 /
									1024
								).toFixed(1)}{" "}
								MB / {data?.memory_mb} MB
							</dd>
						</div>
					</dl>
					<ErrorBox error={attempt?.failure_reason} />
				</Panel>
				<Panel
					title="Attempt history"
					subtitle="Execution retries retain their own logs and results."
				>
					{data?.attempts?.length ? (
						<div className="attempts">
							{data.attempts.map((a: Row, i: number) => (
								<button
									key={a.id}
									className={attempt?.id === a.id ? "selected" : ""}
									onClick={() => setAttemptIndex(i)}
								>
									<span className="attempt-number">{i + 1}</span>
									<div>
										<strong>Attempt {i + 1}</strong>
										<small>{stamp(a.started_at || a.created_at)}</small>
									</div>
									<Badge status={a.status} />
								</button>
							))}
						</div>
					) : (
						<div className="quiet-empty">
							<Clock3 size={20} />
							<p>Waiting for an execution worker.</p>
						</div>
					)}
				</Panel>
			</div>
			<div className="filter-tabs detail-tabs">
				{["logs", "statistics", "configuration"].map((t) => (
					<button
						key={t}
						className={tab === t ? "selected" : ""}
						onClick={() => setTab(t)}
					>
						{t}
					</button>
				))}
			</div>
			<Panel
				title={
					tab === "logs"
						? "Execution logs"
						: tab === "statistics"
							? "Scrapy statistics"
							: "Execution configuration"
				}
			>
				{tab === "logs" ? (
					attempt ? (
						<LogViewer key={attempt.id} kind="attempt" id={attempt.id} />
					) : (
						<div className="quiet-empty">Logs will appear after dispatch.</div>
					)
				) : tab === "statistics" ? (
					<div className="table-scroll">
						<table>
							<thead>
								<tr>
									<th>Metric</th>
									<th>Value</th>
								</tr>
							</thead>
							<tbody>
								{Object.entries(stats).map(([k, v]) => (
									<tr key={k}>
										<td className="mono">{k}</td>
										<td className="mono">{String(v)}</td>
									</tr>
								))}
							</tbody>
						</table>
						{!Object.keys(stats).length && (
							<Empty
								title="Awaiting statistics"
								text="Metrics arrive as the spider runs and when it closes."
							/>
						)}
					</div>
				) : (
					<pre className="config-view">
						{JSON.stringify(
							{
								arguments: data?.arguments,
								settings: data?.settings,
								timeout: data?.timeout,
								cpu: data?.cpu,
								memory_mb: data?.memory_mb,
								max_retries: data?.max_retries,
							},
							null,
							2,
						)}
					</pre>
				)}
			</Panel>
		</>
	);
}
export function Schedules() {
	const { data, error } = useData("schedules", "/schedules");
	const [open, setOpen] = useState(false);
	const [actionError, setError] = useState<unknown>();
	const qc = useQueryClient();
	return (
		<>
			<Heading
				eyebrow="AUTOMATION"
				title="Schedules"
				description="Reliable crawls, on your clock. Persisted across restarts."
				actions={
					<button className="button primary" onClick={() => setOpen(true)}>
						<Plus size={16} /> Create schedule
					</button>
				}
			/>
			<ErrorBox error={error || actionError} />
			<Panel
				title="Scheduled executions"
				subtitle="Deployment-pinned schedules with transactional dispatch."
			>
				{data?.items?.length ? (
					<div className="table-scroll">
						<table>
							<thead>
								<tr>
									<th>Schedule / spider</th>
									<th>Expression</th>
									<th>Next execution</th>
									<th>Overlap</th>
									<th>Enabled</th>
									<th />
								</tr>
							</thead>
							<tbody>
								{data.items.map((s: Row) => (
									<tr key={s.id}>
										<td>
											<strong>{s.name}</strong>
											<span className="table-secondary">{s.spider}</span>
										</td>
										<td>
											<code>{s.cron || "One-time"}</code>
											<span className="table-secondary">{s.timezone}</span>
										</td>
										<td>{s.enabled ? stamp(s.next_run_at) : "Paused"}</td>
										<td>{s.overlap}</td>
										<td>
											<button
												className={`toggle ${s.enabled ? "on" : ""}`}
												role="switch"
												aria-checked={s.enabled}
												aria-label={`Enable ${s.name}`}
												onClick={async () => {
													try {
														await api(
															`/schedules/${s.id}?enabled=${!s.enabled}`,
															{ method: "PATCH" },
														);
														await qc.invalidateQueries();
													} catch (err) {
														setError(err);
													}
												}}
											>
												<span />
											</button>
										</td>
										<td>
											<Link className="text-link" to={`/jobs?schedule=${s.id}`}>
												History <ArrowRight size={13} />
											</Link>
										</td>
									</tr>
								))}
							</tbody>
						</table>
					</div>
				) : (
					<Empty
						title="Put your crawls on a schedule"
						text="Create cron or one-time schedules with timezone, overlap, and retry controls."
						action={
							<button className="button" onClick={() => setOpen(true)}>
								<Plus size={15} /> Create schedule
							</button>
						}
					/>
				)}
			</Panel>
			{open && <RunDialog schedule close={() => setOpen(false)} />}
		</>
	);
}
function Workers() {
	const { data, error } = useQuery<Row[]>({
		queryKey: ["workers"],
		queryFn: () => api("/workers"),
	});
	return (
		<>
			<Heading
				eyebrow="INFRASTRUCTURE"
				title="Workers"
				description="Outbound-connected agents. Isolated Docker execution."
			/>
			<ErrorBox error={error} />
			{data?.length ? (
				<div className="worker-grid">
					{data.map((w) => (
						<div className="panel worker-card" key={w.id}>
							<div className="worker-heading">
								<span className="worker-icon">
									<Server size={25} />
								</span>
								<Badge status={w.online ? "ONLINE" : "OFFLINE"} />
							</div>
							<h2>{w.name}</h2>
							<p>
								{w.kind === "builder"
									? "Image build & discovery agent"
									: "Docker execution agent"}
							</p>
							<dl className="details-list">
								<div>
									<dt>Docker</dt>
									<dd className={w.docker_available ? "green-text" : "muted"}>
										{w.docker_available ? "Available" : "Unavailable"}
									</dd>
								</div>
								<div>
									<dt>CPU capacity</dt>
									<dd>{w.capacity.cpu || 0} cores</dd>
								</div>
								<div>
									<dt>Memory</dt>
									<dd>
										{((w.capacity.memory_bytes || 0) / 1024 ** 3).toFixed(1)} GB
									</dd>
								</div>
								<div>
									<dt>Running containers</dt>
									<dd>{w.capacity.containers_running || 0}</dd>
								</div>
								<div>
									<dt>Execution slots</dt>
									<dd>{w.capacity.slots || 1}</dd>
								</div>
								<div>
									<dt>Last heartbeat</dt>
									<dd>{stamp(w.heartbeat_at)}</dd>
								</div>
							</dl>
						</div>
					))}
				</div>
			) : (
				<Empty
					title="Connect your execution plane"
					text="Start the worker and builder services with Docker Compose. Agents register automatically."
				/>
			)}
			<div className="info-note section-gap">
				<ShieldCheck size={18} />
				<span>
					Agents initiate outbound requests to the API. The dashboard never
					accesses Docker sockets or daemon credentials.
				</span>
			</div>
		</>
	);
}
function Monitoring() {
	const jobs = useData("jobs", "/jobs?limit=200");
	const errors = (jobs.data?.items || []).filter((j: Row) =>
		["FAILED", "TIMED_OUT", "LOST"].includes(j.status),
	);
	return (
		<>
			<Heading
				eyebrow="OPERATIONS"
				title="Monitoring"
				description="Inspect failures and drill into Scrapy statistics for each execution."
			/>
			<ErrorBox error={jobs.error} />
			<Panel
				title="Recent failures"
				subtitle="Failed, timed out, and lost executions from the most recent 200 jobs."
			>
				<JobTable jobs={errors} />
			</Panel>
			<div className="info-note section-gap">
				<Activity size={18} />
				<span>
					Open any execution to inspect live Scrapy counters, response status
					distribution, errors, retries, and container memory usage. Automated
					stall detection and Prometheus export are deferred.
				</span>
			</div>
		</>
	);
}
function Alerts() {
	return (
		<>
			<Heading
				eyebrow="OPERATIONS"
				title="Alerts"
				description="Execution health and notification integrations."
			/>
			<Panel title="Notification integrations">
				<Empty
					title="Alert delivery is not enabled in this release"
					text="Use Monitoring to inspect failed executions. Configurable stall rules, notification channels, and automated alert delivery are planned; no background alert checks run yet."
					action={
						<Link className="button" to="/monitoring">
							<Activity size={15} /> View execution health
						</Link>
					}
				/>
			</Panel>
		</>
	);
}
function Settings() {
	const { data: user } = useData("user", "/auth/me");
	const envs = useQuery<Row[]>({
		queryKey: ["environments"],
		queryFn: () => api("/environments"),
	});
	const tokens = useQuery<Row[]>({
		queryKey: ["tokens"],
		queryFn: () => api("/tokens"),
	});
	const qc = useQueryClient();
	const [error, setError] = useState<unknown>();
	const [created, setCreated] = useState("");
	const [busy, setBusy] = useState(false);
	return (
		<>
			<Heading
				eyebrow="WORKSPACE"
				title="Settings"
				description="Access credentials and secure execution environments."
			/>
			<ErrorBox error={error} />
			<div className="detail-grid">
				<Panel title="Your account">
					<dl className="details-list">
						<div>
							<dt>Email</dt>
							<dd>{user?.email}</dd>
						</div>
						<div>
							<dt>Role</dt>
							<dd>{user?.role}</dd>
						</div>
						<div>
							<dt>API reference</dt>
							<dd>
								<a
									className="text-link"
									href="/docs"
									target="_blank"
									rel="noreferrer"
								>
									OpenAPI documentation <ExternalLink size={12} />
								</a>
							</dd>
						</div>
					</dl>
				</Panel>
				<Panel
					title="API tokens"
					subtitle="Tokens inherit your role. Save new tokens immediately."
				>
					<form
						className="panel-form"
						onSubmit={async (e) => {
							e.preventDefault();
							const f = new FormData(e.currentTarget);
							try {
								const r = await post("/tokens", { name: f.get("name") });
								setCreated(r.token);
								await qc.invalidateQueries({ queryKey: ["tokens"] });
							} catch (err) {
								setError(err);
							}
						}}
					>
						<div className="inline-form">
							<input
								name="name"
								placeholder="Token name"
								aria-label="Token name"
								required
							/>
							<button className="button" type="submit">
								<Plus size={14} /> Create
							</button>
						</div>
					</form>
					{created && (
						<div className="token-result">
							<code>{created}</code>
							<IconButton
								title="Copy token"
								onClick={() => void navigator.clipboard.writeText(created)}
							>
								<Copy size={14} />
							</IconButton>
						</div>
					)}
					<div className="token-list">
						{tokens.data?.map((t) => (
							<div key={t.id}>
								<span>
									{t.name}
									<small>{t.expires_at ? "Session token" : "API token"}</small>
								</span>
								<button
									className="button small danger"
									onClick={async () => {
										try {
											await api(`/tokens/${t.id}`, { method: "DELETE" });
											await qc.invalidateQueries({ queryKey: ["tokens"] });
										} catch (err) {
											setError(err);
										}
									}}
								>
									Revoke
								</button>
							</div>
						))}
					</div>
				</Panel>
			</div>
			<Panel
				title="Execution environments"
				subtitle="Variables and encrypted secrets are injected only into the selected job."
			>
				{envs.data?.length ? (
					<div className="environment-list">
						{envs.data.map((env) => (
							<div key={env.id}>
								<strong>{env.name}</strong>
								<span>
									{Object.keys(env.variables).length} variables ·{" "}
									{env.secret_names.length} secrets
								</span>
							</div>
						))}
					</div>
				) : (
					<div className="quiet-empty">
						<ShieldCheck size={20} />
						<p>No execution environments configured.</p>
					</div>
				)}
				{user?.role === "admin" && (
					<form
						className="panel-form"
						onSubmit={async (e) => {
							e.preventDefault();
							const form = e.currentTarget;
							const f = new FormData(form);
							setBusy(true);
							try {
								await post("/environments", {
									name: f.get("name"),
									variables: JSON.parse(String(f.get("variables"))),
									secrets: JSON.parse(String(f.get("secrets"))),
								});
								form.reset();
								await qc.invalidateQueries();
							} catch (err) {
								setError(err);
							} finally {
								setBusy(false);
							}
						}}
					>
						<Field label="Environment name">
							<input name="name" required placeholder="production" />
						</Field>
						<div className="form-grid">
							<Field label="Variables (JSON)">
								<textarea
									className="mono"
									name="variables"
									defaultValue="{}"
									rows={3}
								/>
							</Field>
							<Field
								label="Secrets (JSON)"
								hint="Encrypted at rest. Values are never returned to the dashboard."
							>
								<textarea
									className="mono"
									name="secrets"
									defaultValue="{}"
									rows={3}
								/>
							</Field>
						</div>
						<FormAction busy={busy} label="Create environment" />
					</form>
				)}
			</Panel>
		</>
	);
}

const root = document.getElementById("root");
if (root)
	createRoot(root).render(
		<React.StrictMode>
			<QueryClientProvider client={client}>
				<BrowserRouter>
					<App />
				</BrowserRouter>
			</QueryClientProvider>
		</React.StrictMode>,
	);
