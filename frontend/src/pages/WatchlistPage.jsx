import { useEffect, useState } from "react";
import { getWatchlist, getScreening, refreshScreening, getWatchCodes, addWatchCode, removeWatchCode } from "../api";
import s from "./Page.module.css";
import BacktestModal from "./BacktestModal";

/* ── 스크리닝 시그널 배지 ─────────────────────────────── */
const SIGNALS = {
  golden_cross:     { label: "골든크로스", color: "#f59e0b" },
  ma_uptrend:       { label: "정배열",     color: "#10b981" },
  long_bull:        { label: "장대양봉",   color: "#ef4444" },
  resistance_break: { label: "저항돌파",   color: "#8b5cf6" },
  volume_breakout:  { label: "거래량돌파", color: "#3b82f6" },
  volume_surge:     { label: "거래량급등", color: "#f97316" },
  price_surge:      { label: "주가급등",   color: "#ec4899" },
};

function ScoreBar({ score }) {
  const pct   = Math.round((score / 7) * 100);
  const color = score >= 5 ? "#ef4444" : score >= 3 ? "#f59e0b" : "#6b7280";
  return (
    <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
      <div style={{ width: 52, height: 5, background: "#374151", borderRadius: 3, overflow: "hidden" }}>
        <div style={{ width: `${pct}%`, height: "100%", background: color }} />
      </div>
      <span style={{ color, fontWeight: 700, fontSize: 12 }}>{score}/7</span>
    </div>
  );
}

function Badges({ item }) {
  const active = Object.entries(SIGNALS).filter(([k]) => item[k]);
  if (!active.length) return <span style={{ color: "#6b7280", fontSize: 11 }}>–</span>;
  return (
    <div style={{ display: "flex", flexWrap: "wrap", gap: 3 }}>
      {active.map(([k, { label, color }]) => (
        <span key={k} style={{
          background: color + "22", color, border: `1px solid ${color}55`,
          borderRadius: 4, padding: "1px 5px", fontSize: 10, whiteSpace: "nowrap",
        }}>{label}</span>
      ))}
    </div>
  );
}

function NextUpdate() {
  const h = new Date().getHours();
  const next = h < 9 ? "09:00" : h < 12 ? "12:00" : h < 15 ? "15:00" : "내일 09:00";
  return <span style={{ color: "#6b7280", fontSize: 12 }}>다음 갱신 {next}</span>;
}

/* ── 섹션 구분선 ─────────────────────────────────────── */
function Divider({ label }) {
  return (
    <div style={{
      display: "flex", alignItems: "center", gap: 10,
      margin: "28px 0 16px",
    }}>
      <div style={{ flex: 1, height: 1, background: "var(--border)" }} />
      <span style={{ color: "var(--muted)", fontSize: 12, whiteSpace: "nowrap" }}>{label}</span>
      <div style={{ flex: 1, height: 1, background: "var(--border)" }} />
    </div>
  );
}

/* ── 감시 종목 설정 모달 ─────────────────────────────── */
function WatchSettingsModal({ onClose, onChanged }) {
  const [codes,    setCodes]    = useState([]);
  const [names,    setNames]    = useState({});  // code → name (watchlist에서 캐시)
  const [newCode,  setNewCode]  = useState("");
  const [error,    setError]    = useState("");
  const [loading,  setLoading]  = useState(true);
  const [adding,   setAdding]   = useState(false);
  const [deleting, setDeleting] = useState(null); // 삭제 중인 코드

  useEffect(() => {
    (async () => {
      try {
        const r = await getWatchCodes();
        setCodes(r.data.codes ?? []);
      } catch {}
      setLoading(false);
    })();
  }, []);

  async function handleAdd() {
    const code = newCode.trim();
    if (!/^\d{6}$/.test(code)) { setError("6자리 숫자 코드를 입력하세요 (예: 005930)"); return; }
    if (codes.includes(code))  { setError("이미 등록된 종목입니다."); return; }
    setError(""); setAdding(true);
    try {
      await addWatchCode(code);
      setCodes(prev => [...prev, code].sort());
      setNewCode("");
      onChanged();
    } catch { setError("추가 실패 — 서버 오류"); }
    setAdding(false);
  }

  async function handleDelete(code) {
    setDeleting(code);
    try {
      await removeWatchCode(code);
      setCodes(prev => prev.filter(c => c !== code));
      onChanged();
    } catch {}
    setDeleting(null);
  }

  function handleKeyDown(e) {
    if (e.key === "Enter") handleAdd();
  }

  return (
    <div className={s.overlay} onClick={e => e.target === e.currentTarget && onClose()}>
      <div className={s.modal}>
        <div className={s.modalHeader}>
          <span className={s.modalTitle}>⚙️ 감시 종목 설정</span>
          <button className={s.modalClose} onClick={onClose}>×</button>
        </div>

        <div className={s.modalBody}>
          {loading && <div className={s.loading} style={{ padding: "24px 0" }}>불러오는 중...</div>}

          {!loading && codes.length === 0 && (
            <div className={s.emptyCode}>등록된 감시 종목이 없습니다.</div>
          )}

          {!loading && codes.map(code => (
            <div key={code} className={s.watchCodeRow}>
              <span className={s.watchCodeName}>
                {names[code] ?? code}
              </span>
              <span className={s.watchCodeNum}>{names[code] ? code : ""}</span>
              <button
                className={s.deleteBtn}
                onClick={() => handleDelete(code)}
                disabled={deleting === code}
              >
                {deleting === code ? "…" : "삭제"}
              </button>
            </div>
          ))}

          <div className={s.addRow}>
            <input
              className={s.codeInput}
              value={newCode}
              onChange={e => { setNewCode(e.target.value); setError(""); }}
              onKeyDown={handleKeyDown}
              placeholder="종목코드 입력 (예: 005930)"
              maxLength={6}
            />
            <button className={s.addBtn} onClick={handleAdd} disabled={adding}>
              {adding ? "..." : "+ 추가"}
            </button>
          </div>
          {error && <div className={s.inputError}>{error}</div>}
        </div>

        <div className={s.modalFooter}>
          <button className={s.refreshBtn} onClick={onClose} style={{ width: "100%" }}>
            완료
          </button>
        </div>
      </div>
    </div>
  );
}

/* ── 메인 컴포넌트 ───────────────────────────────────── */
export default function WatchlistPage({ onSelect }) {
  const [watchData,    setWatchData]    = useState(null);
  const [screenData,   setScreenData]   = useState(null);
  const [watchLoading, setWatchLoading] = useState(true);
  const [refreshing,   setRefreshing]   = useState(false);
  const [showSettings, setShowSettings] = useState(false);
  const [backtestCode, setBacktestCode] = useState(null);  // 백테스트 대상 종목코드
  const [backtestName, setBacktestName] = useState("");

  async function loadWatch() {
    setWatchLoading(true);
    try { const r = await getWatchlist();  setWatchData(r.data); } catch {}
    setWatchLoading(false);
  }

  async function loadScreen() {
    try { const r = await getScreening(); setScreenData(r.data); } catch {}
  }

  async function handleRefreshScreen() {
    setRefreshing(true);
    try {
      await refreshScreening();
      await loadScreen();   // 즉시 running=true 상태 수신 → 자동 폴링이 이어받음
    } catch {}
    setRefreshing(false);
  }

  useEffect(() => {
    loadWatch();
    loadScreen();
  }, []);

  // 스크리너 실행 중일 때 3초마다 자동 재조회
  useEffect(() => {
    if (!screenData?.running) return;
    const timer = setInterval(async () => {
      try {
        const r = await getScreening();
        setScreenData(r.data);
      } catch {}
    }, 3000);
    return () => clearInterval(timer);
  }, [screenData?.running]);

  return (
    <div>
      {showSettings && (
        <WatchSettingsModal
          onClose={() => setShowSettings(false)}
          onChanged={loadWatch}
        />
      )}
      {backtestCode && (
        <BacktestModal
          code={backtestCode}
          name={backtestName}
          onClose={() => setBacktestCode(null)}
        />
      )}

      {/* ── 감시 종목 섹션 ────────────────────────── */}
      <div className={s.toolbar}>
        <h2 className={s.pageTitle}>📌 내 감시 종목</h2>
        {watchData && <span className={s.updated}>업데이트: {watchData.updated}</span>}
        <button className={s.refreshBtn} onClick={loadWatch}>↻</button>
        <button className={s.refreshBtn} onClick={() => setShowSettings(true)} title="감시 종목 설정">⚙️</button>
      </div>

      {watchLoading && <div className={s.loading}>불러오는 중...</div>}

      {watchData?.error && (
        <div className={s.empty}>감시 종목 조회 실패: {watchData.error}</div>
      )}

      {watchData?.watchlist && (
        <div className={s.grid4}>
          {watchData.watchlist.length === 0 && !watchLoading && (
            <div className={s.empty} style={{ gridColumn: "1 / -1" }}>
              감시 종목 없음 — 텔레그램 /watch 명령으로 추가하세요
            </div>
          )}
          {watchData.watchlist.map(item => (
            <div
              key={item.code}
              className={`${s.card} ${s.clickable}`}
              onClick={() => onSelect(item.code)}
            >
              <div className={s.cardHeader}>
                <span className={s.name}>{typeof item.name === "string" ? item.name : item.code}</span>
                <span className={s.code}>{item.code}</span>
              </div>
              <div className={s.price}>{item.price?.toLocaleString()}원</div>
              <div className={`${s.change} ${item.change_pct >= 0 ? s.up : s.down}`}>
                {item.change_pct >= 0 ? "▲" : "▼"} {Math.abs(item.change_pct).toFixed(2)}%
              </div>
              <div className={s.meta}>
                <span>거래량 {item.volume_ratio?.toFixed(1)}배</span>
                {item.signal !== "–" && <span className={s.signal}>{item.signal}</span>}
              </div>
            </div>
          ))}
        </div>
      )}

      {/* ── 구분선 ───────────────────────────────── */}
      <Divider label="자동 스크리닝 — KOSPI 시총 상위 100개 분석" />

      {/* ── 스크리닝 섹션 ─────────────────────────── */}
      <div className={s.toolbar} style={{ marginBottom: 12 }}>
        <h2 className={s.pageTitle}>🔍 기술점수 상위 10종목</h2>
        <div style={{ marginLeft: "auto", display: "flex", alignItems: "center", gap: 10 }}>
          {screenData?.updated_at && (
            <span className={s.updated}>갱신: {screenData.updated_at}</span>
          )}
          <NextUpdate />
          <button
            className={s.refreshBtn}
            onClick={handleRefreshScreen}
            disabled={refreshing || screenData?.running}
          >
            {refreshing || screenData?.running ? "분석 중..." : "⚡ 재분석"}
          </button>
        </div>
      </div>

      {/* 캐시 없을 때 */}
      {!screenData?.screened?.length && !screenData?.running && (
        <div className={s.empty} style={{ padding: "20px 0" }}>
          스크리닝 결과 없음 — ⚡ 재분석 버튼을 눌러 시작하세요
        </div>
      )}

      {screenData?.running && (
        <div className={s.loading} style={{ padding: "16px 0" }}>
          분석 중... (시총 상위 100종목 기술적 분석 중)
        </div>
      )}

      {screenData?.screened?.length > 0 && (
        <table className={s.table}>
          <thead>
            <tr>
              <th>#</th>
              <th>종목명</th>
              <th>현재가</th>
              <th>등락률</th>
              <th>거래량 배수</th>
              <th>기술점수</th>
              <th>시그널</th>
              <th style={{ minWidth: 140 }}></th>
            </tr>
          </thead>
          <tbody>
            {screenData.screened.map((item, i) => (
              <tr
                key={item.code}
                className={s.clickableRow}
                onClick={() => onSelect(item.code)}
              >
                <td className={s.muted}>{i + 1}</td>
                <td className={s.name}>
                  {typeof item.name === "string" ? item.name : item.code}
                  <span className={s.code} style={{ marginLeft: 6 }}>{item.code}</span>
                </td>
                <td>{item.price?.toLocaleString()}원</td>
                <td className={item.change_pct >= 0 ? s.up : s.down}>
                  {item.change_pct >= 0 ? "▲" : "▼"} {Math.abs(item.change_pct).toFixed(2)}%
                </td>
                <td className={item.volume_ratio >= 3 ? s.up : ""}>
                  {item.volume_ratio?.toFixed(1)}배
                </td>
                <td><ScoreBar score={item.total_score ?? 0} /></td>
                <td><Badges item={item} /></td>
                <td onClick={(e) => e.stopPropagation()} style={{ display: "flex", gap: 6 }}>
                  <button className={s.smallBtn} onClick={() => onSelect(item.code)}>차트 →</button>
                  <button
                    className={s.smallBtn}
                    style={{ background: "var(--accent)22", color: "var(--accent)", borderColor: "var(--accent)44" }}
                    onClick={() => { setBacktestCode(item.code); setBacktestName(typeof item.name === "string" ? item.name : item.code); }}
                  >백테스트</button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  );
}
