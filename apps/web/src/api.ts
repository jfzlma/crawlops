export type Row = Record<string, any>;
export function token() {
	return sessionStorage.getItem("crawlops-token") || "";
}
export async function api(path: string, options: RequestInit = {}) {
	const headers: Record<string, string> = {
		Authorization: `Bearer ${token()}`,
	};
	if (options.body && !(options.body instanceof FormData))
		headers["Content-Type"] = "application/json";
	const response = await fetch(`/api${path}`, {
		...options,
		headers: { ...headers, ...options.headers },
	});
	if (!response.ok) {
		let message = `Request failed (${response.status})`;
		try {
			const data = await response.json();
			message =
				typeof data.detail === "string"
					? data.detail
					: JSON.stringify(data.detail);
		} catch {
			/* use status */
		}
		if (response.status === 401 && path !== "/auth/login") {
			sessionStorage.removeItem("crawlops-token");
			window.dispatchEvent(new Event("auth-change"));
		}
		throw new Error(message);
	}
	return response.json();
}
export function post(path: string, body: unknown = {}) {
	return api(path, { method: "POST", body: JSON.stringify(body) });
}
export function stamp(value?: string) {
	return value
		? new Date(value).toLocaleString([], {
				month: "short",
				day: "numeric",
				hour: "2-digit",
				minute: "2-digit",
			})
		: "—";
}
export function short(value?: string) {
	return value ? value.slice(0, 8) : "—";
}
