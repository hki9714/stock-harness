import { useState, Component } from "react";
import WatchlistPage    from "./pages/WatchlistPage";
import ChartPage        from "./pages/ChartPage";
import FinancialPage    from "./pages/FinancialPage";
import SentimentPage    from "./pages/SentimentPage";
import ScreeningPage    from "./pages/ScreeningPage";
import DevConsolePage   from "./pages/DevConsolePage";
import styles           from "./App.module.css";

class ErrorBoundary extends Component {
  constructor(props) {
    super(props);
    this.state = { error: null };
  }
  static getDerivedStateFromError(error) { return { error }; }
  render() {
    if (this.state.error) {
      return (
        <div style={{ padding: 40, color: "#ef4444", fontFamily: "monospace" }}>
          <h2 style={{ marginBottom: 12 }}>⚠️ 렌더링 오류</h2>
          <pre style={{ fontSize: 12, whiteSpace: "pre-wrap", background: "#1f2937", padding: 16, borderRadius: 6 }}>
            {this.state.error.message}
          </pre>
          <button
            onClick={() => this.setState({ error: null })}
            style={{ marginTop: 16, padding: "6px 16px", cursor: "pointer" }}
          >
            다시 시도
          </button>
        </div>
      );
    }
    return this.props.children;
  }
}

const TABS = [
  { id: "watchlist",  label: "📊 감시 종목" },
  { id: "chart",      label: "📈 차트 분석" },
  { id: "financial",  label: "💰 재무제표" },
  { id: "sentiment",  label: "💬 감성 분석" },
  { id: "screening",  label: "🔍 스크리닝"  },
  { id: "dev",        label: "🛠️ Dev Console" },
];

export default function App() {
  const [tab,          setTab]  = useState("watchlist");
  const [selectedCode, setCode] = useState(null);

  function selectStock(code) {
    setCode(code);
    setTab("chart");
  }

  return (
    <div className={styles.app}>
      {/* 헤더 */}
      <header className={styles.header}>
        <h1 className={styles.title}>📈 Stock <span>Harness</span></h1>
        <nav className={styles.tabs}>
          {TABS.map(t => (
            <button
              key={t.id}
              className={`${styles.tab} ${tab === t.id ? styles.active : ""}`}
              onClick={() => setTab(t.id)}
            >
              {t.label}
            </button>
          ))}
        </nav>
      </header>

      {/* 본문 */}
      <main className={`${styles.main} ${tab === "dev" ? styles.mainFull : ""}`}>
        <ErrorBoundary key={tab}>
          {tab === "watchlist" && <WatchlistPage  onSelect={selectStock} />}
          {tab === "chart"     && <ChartPage      code={selectedCode} />}
          {tab === "financial" && <FinancialPage  code={selectedCode} />}
          {tab === "sentiment" && <SentimentPage  code={selectedCode} />}
          {tab === "screening" && <ScreeningPage  onSelect={selectStock} />}
          {tab === "dev"       && <DevConsolePage />}
        </ErrorBoundary>
      </main>
    </div>
  );
}
