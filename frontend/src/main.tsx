import React, { useEffect, useRef, useState } from "react";
import { createRoot } from "react-dom/client";
import "./style.css";

type Account = {
  id: string;
  label: string;
  server: string;
  login_suffix: string;
  status: string;
  margin_mode: string;
  selected: boolean;
  last_seen_at: string | null;
  ea_version: string | null;
  execution_enabled: boolean;
  mappings: { alias: string; actual_symbol: string }[];
};
type Operation = {
  id: string;
  account_id: string;
  type: string;
  status: string;
  created_at: string;
  payload: { symbol: string; side: string; target_fraction: number };
  summary: null | {
    code: string;
    planned_volume: number;
    confirmed_volume: number;
  };
};
async function api(path: string, init?: RequestInit) {
  const response = await fetch("/v1/web" + path, {
    credentials: "same-origin",
    ...init,
    headers: { "Content-Type": "application/json", ...init?.headers },
  });
  if (!response.ok) {
    const body = await response
      .json()
      .catch(() => ({ detail: "Service unavailable" }));
    throw new Error(body.detail || "Request failed");
  }
  return response.json();
}
function App() {
  type View = "overview" | "accounts" | "activity";
  const readView = (): View => {
    const hash = window.location.hash.slice(1);
    return hash === "accounts" || hash === "activity" ? hash : "overview";
  };
  const [view, setView] = useState<View>(readView);
  useEffect(() => {
    const changed = () => setView(readView());
    window.addEventListener("hashchange", changed);
    return () => window.removeEventListener("hashchange", changed);
  }, []);
  const [accounts, setAccounts] = useState<Account[]>([]),
    [history, setHistory] = useState<Operation[]>([]);
  const [logged, setLogged] = useState(false),
    [loading, setLoading] = useState(true),
    [error, setError] = useState("");
  const [selected, setSelected] = useState<string>(""),
    [alias, setAlias] = useState("gold"),
    [symbol, setSymbol] = useState("");
  const [revoke, setRevoke] = useState<string | null>(null),
    [busy, setBusy] = useState(false);
  const loginRef = useRef<HTMLDivElement>(null);
  const [distribution, setDistribution] = useState<{
    bot_username: string;
    ea_download_url: string;
    setup_url: string;
  } | null>(null);
  async function refresh() {
    try {
      const [a, h] = await Promise.all([api("/accounts"), api("/history")]);
      setAccounts(a);
      setHistory(h);
      setLogged(true);
      setError("");
    } catch (e) {
      if ((e as Error).message === "LOGIN_REQUIRED") setLogged(false);
      else setError((e as Error).message);
    } finally {
      setLoading(false);
    }
  }
  useEffect(() => {
    void refresh();
    const timer = setInterval(() => void refresh(), 5000);
    return () => clearInterval(timer);
  }, []);
  useEffect(() => {
    if (logged || loading || !loginRef.current) return;
    // Telegram sends signed login fields to this same-origin page via redirect.
    const params = new URLSearchParams(window.location.search);
    if (params.has("hash")) {
      const fields: Record<string, string | number> = {};
      params.forEach((v, k) => {
        fields[k] = ["id", "auth_date"].includes(k) ? Number(v) : v;
      });
      window.history.replaceState({}, "", window.location.pathname);
      void api("/login", { method: "POST", body: JSON.stringify(fields) })
        .then(refresh)
        .catch((e) => setError(e.message));
      return;
    }
    void fetch("/v1/config")
      .then((r) => r.json())
      .then((config) => {
        setDistribution(config);
        if (!config.bot_username || !loginRef.current) return;
        const script = document.createElement("script");
        script.src = "https://telegram.org/js/telegram-widget.js?22";
        script.setAttribute("data-telegram-login", config.bot_username);
        script.setAttribute("data-size", "large");
        script.setAttribute("data-radius", "20");
        script.setAttribute("data-auth-url", window.location.origin + "/");
        script.async = true;
        loginRef.current.replaceChildren(script);
      })
      .catch(() => setError("Unable to load sign-in settings."));
  }, [logged, loading]);
  async function mutate(path: string, method = "POST", body?: unknown) {
    setBusy(true);
    setError("");
    try {
      await api(path, {
        method,
        body: body ? JSON.stringify(body) : undefined,
      });
      setRevoke(null);
      await refresh();
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }
  const online = accounts.filter((a) => a.status === "ONLINE").length;
  return (
    <div className="shell">
      <aside>
        <a className="brand" href="/">
          <span className="mark">A</span>anchor<span className="dot">.</span>
        </a>
        <div className="workspace">MT5 RISK CONTROL</div>
        <nav>
          {(["overview", "accounts", "activity"] as const).map((item) => (
            <a
              key={item}
              href={`#${item}`}
              className={view === item ? "active" : ""}
              aria-current={view === item ? "page" : undefined}
            >
              <span>
                {item === "overview"
                  ? "Overview"
                  : item === "accounts"
                    ? "Accounts"
                    : "Activity"}
              </span>
            </a>
          ))}
        </nav>
        <div className="sidebar-note">
          <span className="small-dot" /> Risk reduction only
          <p>Trade controls live in your Telegram conversation.</p>
        </div>
      </aside>
      <main>
        <header>
          <span className="eyebrow">YOUR TRADING WORKSPACE</span>
          <span className="pill">MVP · Protocol 1</span>
        </header>
        <div className="title-row">
          <div>
            <h1>
              {view === "overview"
                ? "Stay in control."
                : view === "accounts"
                  ? "Your accounts."
                  : "Your activity."}
            </h1>
            <p className="subtitle">
              A clear view of your accounts, protection requests, and outcomes.
            </p>
          </div>
          <div className="live-indicator">
            <span className="small-dot" />
            {logged ? "Updates every 5 seconds" : "Secure Telegram sign-in"}
          </div>
        </div>
        {error && (
          <div className="error" role="alert">
            {error}
          </div>
        )}
        {!logged ? (
          <section className="welcome">
            <div className="eyebrow">CONNECTED TO YOU. EXECUTED IN MT5.</div>
            <h2>
              {view === "overview" ? (
                <>
                  Your terminal.
                  <br />
                  Your control.
                </>
              ) : view === "accounts" ? (
                "Sign in to view your accounts"
              ) : (
                "Sign in to view your activity"
              )}
            </h2>
            <p>
              Pair an agent with <code>/link</code> in Telegram, then sign in
              here to manage exact symbol mappings and review results.
            </p>
            {distribution && (
              <div className="onboarding-links">
                {distribution.bot_username && (
                  <a href={`https://t.me/${distribution.bot_username}`}>
                    Open Telegram bot ↗
                  </a>
                )}
                <a href={distribution.ea_download_url}>Download EA source ↓</a>
                <a href={distribution.setup_url}>Installation guide ↗</a>
              </div>
            )}
            <div ref={loginRef} />
            <details className="login-help">
              <summary>Telegram sign-in not working?</summary>
              <p>
                If Telegram shows “Bot domain invalid”, the bot owner should
                open the @BotFather mini app, select
                <code> @{distribution?.bot_username || "your bot"} </code>, then
                Login Widget and check Allowed URLs includes
                <code> {window.location.origin}</code>. Reload after saving. If
                the error persists, contact the operator to check widget
                compatibility. Dashboard sign-in is separate from MT5 agent
                pairing.
              </p>
            </details>
            <p className="muted">
              {loading
                ? "Loading…"
                : "Use the same Telegram account you paired with. Your broker password stays with MT5."}
            </p>
          </section>
        ) : (
          <>
            <div className="stats" hidden={view !== "overview"}>
              <section>
                <span>Connected accounts</span>
                <strong>{accounts.length.toString().padStart(2, "0")}</strong>
                <small>Paired to your Telegram identity</small>
              </section>
              <section>
                <span>Agents online</span>
                <strong>
                  {online.toString().padStart(2, "0")}
                  <i className="small-dot" />
                </strong>
                <small>Heartbeat received within 5 seconds</small>
              </section>
              <section>
                <span>Recent operations</span>
                <strong>{history.length.toString().padStart(2, "0")}</strong>
                <small>Preview and execution tracked separately</small>
              </section>
            </div>
            <section className="section" hidden={view === "activity"}>
              <div className="section-heading">
                <h2>
                  Your accounts <span>{accounts.length}</span>
                </h2>
                <p>
                  Add an account with <code>/link</code>
                </p>
              </div>
              {accounts.length === 0 ? (
                <div className="empty">
                  No accounts paired yet. Send <code>/link</code> to the bot and
                  enter the code in your MT5 agent.
                </div>
              ) : (
                <div className="account-grid">
                  {accounts.map((a) => (
                    <article key={a.id} className="account">
                      <div className="card-top">
                        <span className="account-icon">↗</span>
                        <span
                          className={
                            "status " + (a.status === "ONLINE" ? "good" : "")
                          }
                        >
                          {a.status.replaceAll("_", " ")}
                        </span>
                      </div>
                      <h3>{a.label}</h3>
                      <p className="muted">
                        {a.server} · •••• {a.login_suffix}
                      </p>
                      <dl>
                        <div>
                          <dt>Account mode</dt>
                          <dd>
                            {a.margin_mode === "RETAIL_HEDGING"
                              ? "Hedging"
                              : "Unsupported mode"}
                          </dd>
                        </div>
                        <div>
                          <dt>Agent version</dt>
                          <dd>{a.ea_version ?? "Revoked"}</dd>
                        </div>
                        <div>
                          <dt>Execution</dt>
                          <dd>
                            {a.execution_enabled
                              ? "Enabled locally"
                              : "Preview only"}
                          </dd>
                        </div>
                        <div>
                          <dt>Last seen</dt>
                          <dd>
                            {a.last_seen_at
                              ? new Date(a.last_seen_at).toLocaleTimeString()
                              : "Never"}
                          </dd>
                        </div>
                      </dl>
                      <div className="mappings">
                        {a.mappings.length ? (
                          a.mappings.map((m) => (
                            <span key={m.alias}>
                              {m.alias} <b>→</b> {m.actual_symbol}
                            </span>
                          ))
                        ) : (
                          <span>No aliases configured</span>
                        )}
                      </div>
                      <div className="card-actions">
                        <button
                          disabled={busy || a.selected}
                          onClick={() =>
                            void mutate(`/accounts/${a.id}/select`)
                          }
                        >
                          {a.selected ? "✓ Selected" : "Select account"}
                        </button>
                        <button
                          className="text-btn"
                          onClick={() => {
                            setSelected(a.id);
                            setSymbol("");
                          }}
                        >
                          Edit aliases
                        </button>
                        <button
                          className="text-btn danger"
                          onClick={() => setRevoke(a.id)}
                        >
                          Revoke
                        </button>
                      </div>
                    </article>
                  ))}
                </div>
              )}
            </section>
            {selected && (
              <section className="edit-panel">
                <h3>Map an exact broker symbol</h3>
                <p>
                  Copy the symbol exactly from MT5 Market Watch, including any
                  suffix. Applies to the selected account only.
                </p>
                <form
                  onSubmit={(e) => {
                    e.preventDefault();
                    void mutate(`/accounts/${selected}/mappings`, "PUT", {
                      alias,
                      actual_symbol: symbol,
                    }).then(() => setSelected(""));
                  }}
                >
                  <label>
                    Alias
                    <input
                      value={alias}
                      onChange={(e) => setAlias(e.target.value)}
                      required
                      maxLength={64}
                      pattern="[A-Za-z0-9_.#\-]+"
                    />
                  </label>
                  <span>→</span>
                  <label>
                    Exact broker symbol
                    <input
                      value={symbol}
                      onChange={(e) => setSymbol(e.target.value)}
                      placeholder="XAUUSD.a"
                      required
                      maxLength={64}
                    />
                  </label>
                  <button disabled={busy}>Save mapping</button>
                  <button
                    type="button"
                    className="text-btn"
                    onClick={() => setSelected("")}
                  >
                    Cancel
                  </button>
                </form>
              </section>
            )}
            {revoke && (
              <section
                className="edit-panel"
                role="alertdialog"
                aria-label="Revoke agent"
              >
                <h3>Revoke this agent?</h3>
                <p>
                  Future polls will be rejected. An operation already delivered
                  to MT5 may still finish. Any uncertain execution requires
                  reconciliation before re-pairing.
                </p>
                <button
                  disabled={busy}
                  onClick={() => void mutate(`/accounts/${revoke}/revoke`)}
                >
                  Revoke agent
                </button>{" "}
                <button className="text-btn" onClick={() => setRevoke(null)}>
                  Cancel
                </button>
              </section>
            )}
            <section className="section" hidden={view === "accounts"}>
              <div className="section-heading">
                <h2>Recent activity</h2>
                <p>Requested → planned → confirmed</p>
              </div>
              <div className="table-wrap">
                <table>
                  <thead>
                    <tr>
                      <th>Operation</th>
                      <th>Exposure</th>
                      <th>Status</th>
                      <th>Planned / confirmed</th>
                      <th>Time</th>
                    </tr>
                  </thead>
                  <tbody>
                    {history.map((h) => (
                      <tr key={h.id}>
                        <td>
                          <strong>
                            {h.type.includes("REDUCE") ? "Close" : "BE+"}
                          </strong>
                          <small>
                            {h.type.startsWith("PREVIEW")
                              ? "Preview"
                              : "Execution"}{" "}
                            · {h.id.slice(0, 8)}
                          </small>
                        </td>
                        <td>
                          {h.payload.symbol}
                          <small>
                            {h.payload.target_fraction * 100}% ·{" "}
                            {h.payload.side}
                          </small>
                        </td>
                        <td>
                          <span
                            className={
                              "status " +
                              (h.status === "SUCCEEDED" ? "good" : "")
                            }
                          >
                            {h.status.replaceAll("_", " ")}
                          </span>
                        </td>
                        <td>
                          {h.summary
                            ? `${h.summary.planned_volume} / ${h.summary.confirmed_volume} lots`
                            : "—"}
                          <small>{h.summary?.code}</small>
                        </td>
                        <td>{new Date(h.created_at).toLocaleString()}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
                {!history.length && (
                  <div className="empty">
                    Your first preview will appear here.
                  </div>
                )}
              </div>
            </section>
            <section className="command-guide">
              <div>
                <span className="eyebrow">
                  THREE COMMANDS. DELIBERATE CONTROL.
                </span>
                <h2>From Telegram to your terminal.</h2>
              </div>
              <div>
                <code>/link</code>
                <p>Pair an account</p>
              </div>
              <div>
                <code>/be gold 50</code>
                <p>Protect 50% by volume</p>
              </div>
              <div>
                <code>/close gold 50</code>
                <p>Close worst-cost lots first</p>
              </div>
            </section>
          </>
        )}
        <footer>
          <span>anchor · MT5 risk management</span>
          <span>
            BE+ is a buffer estimate. Broker-confirmed outcomes are reported by
            your agent.
          </span>
        </footer>
      </main>
    </div>
  );
}
createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>,
);
