import React from "react";
import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import {
	App,
	DeploymentWizard,
	LogViewer,
	Projects,
	RunDialog,
	Schedules,
} from "./main";
import { api, post } from "./api";
vi.mock("./api", async () => ({
	...(await vi.importActual("./api")),
	api: vi.fn(),
	post: vi.fn(),
}));
const apiMock = vi.mocked(api);
const postMock = vi.mocked(post);
function mount(node: React.ReactNode, path = "/") {
	return render(
		<QueryClientProvider
			client={
				new QueryClient({
					defaultOptions: { queries: { retry: false, refetchInterval: false } },
				})
			}
		>
			<MemoryRouter initialEntries={[path]}>{node}</MemoryRouter>
		</QueryClientProvider>,
	);
}
beforeEach(() => {
	vi.resetAllMocks();
	apiMock.mockImplementation(async (path) => {
		if (path.startsWith("/projects"))
			return {
				items: [{ id: "p1", name: "catalog", description: "Fixture crawler" }],
				total: 1,
			};
		if (path.startsWith("/deployments?"))
			return {
				items: [{ id: "d1", project_id: "p1", version: "v1", status: "READY" }],
				total: 1,
			};
		if (path === "/deployments/d1")
			return { id: "d1", spiders: ["catalog"], status: "READY" };
		if (path === "/environments") return [];
		if (path.startsWith("/logs"))
			return [
				{
					id: "l1",
					sequence: 0,
					text: "2026-01-01 INFO hello\n2026-01-01 ERROR connection failed\n",
				},
			];
		if (path === "/schedules")
			return {
				items: [
					{
						id: "s1",
						name: "Daily catalog",
						spider: "catalog",
						cron: "0 6 * * *",
						timezone: "UTC",
						enabled: true,
						overlap: "forbid",
					},
				],
				total: 1,
			};
		return { items: [], total: 0 };
	});
	postMock.mockResolvedValue({ id: "new" });
});
describe("connected workflows", () => {
	it("shows authentication before workspace navigation", () => {
		mount(<App />);
		expect(screen.getByText("Welcome back.")).toBeTruthy();
		expect(screen.getByLabelText("Password")).toBeTruthy();
	});
	it("renders project records from the API", async () => {
		mount(<Projects />);
		expect(await screen.findByText("catalog")).toBeTruthy();
		expect(screen.getByText("Fixture crawler")).toBeTruthy();
	});
	it("shows actionable API errors", async () => {
		apiMock.mockRejectedValue(new Error("Control plane unavailable"));
		mount(<Projects />);
		expect(await screen.findByRole("alert")).toHaveProperty(
			"textContent",
			"Control plane unavailable",
		);
	});
	it("advances deployment wizard and switches sources", async () => {
		mount(<DeploymentWizard close={() => {}} />);
		fireEvent.click(screen.getByText("Docker image"));
		fireEvent.click(screen.getByText("Continue"));
		expect(
			screen.getByLabelText("Image reference", { exact: false }),
		).toBeTruthy();
		expect(screen.getByLabelText("Version")).toBeTruthy();
	});
	it("submits a real execution specification", async () => {
		mount(<RunDialog close={() => {}} />);
		await waitFor(() =>
			expect(screen.getByLabelText("Spider")).toHaveProperty(
				"value",
				"catalog",
			),
		);
		fireEvent.click(screen.getByText("Start execution"));
		await waitFor(() =>
			expect(postMock).toHaveBeenCalledWith(
				"/jobs",
				expect.objectContaining({
					deployment_id: "d1",
					spider: "catalog",
					memory_mb: 512,
					timeout: 3600,
				}),
			),
		);
	});
	it("filters and pauses the log viewer", async () => {
		mount(<LogViewer kind="attempt" id="a1" />);
		expect(await screen.findByText("2026-01-01 INFO hello")).toBeTruthy();
		fireEvent.change(screen.getByLabelText("Log level"), {
			target: { value: "ERROR" },
		});
		expect(screen.queryByText("2026-01-01 INFO hello")).toBeNull();
		expect(screen.getByText("2026-01-01 ERROR connection failed")).toBeTruthy();
		fireEvent.click(screen.getByText("Pause"));
		expect(screen.getByText("Resume")).toBeTruthy();
	});
	it("toggles persisted schedules through the API", async () => {
		mount(<Schedules />);
		const toggle = await screen.findByRole("switch");
		fireEvent.click(toggle);
		await waitFor(() =>
			expect(apiMock).toHaveBeenCalledWith("/schedules/s1?enabled=false", {
				method: "PATCH",
			}),
		);
	});
	it("previews cron occurrences in the schedule editor", async () => {
		postMock.mockResolvedValue({ next: ["2026-10-14T06:00:00Z"] });
		mount(<RunDialog schedule close={() => {}} />);
		await screen.findByText("v1 · p1");
		fireEvent.click(screen.getByText("Preview next executions"));
		await waitFor(() =>
			expect(postMock).toHaveBeenCalledWith(
				"/schedules/preview",
				expect.objectContaining({ cron: "0 6 * * *", overlap: "forbid" }),
			),
		);
	});
});
