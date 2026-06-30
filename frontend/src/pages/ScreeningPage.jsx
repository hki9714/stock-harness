import { useEffect, useState } from "react";
import { getScreening, refreshScreening } from "../api";
import s from "./Page.module.css";

const SIGNAL_LABELS = {
  golden_cross:     { label: "골든크로스", color: "#f59e0b" },
  ma_uptrend:       { label: "정배열",     color: "#10b981" },
  long_bull:        { label: "장대양봉",   color: "#ef4444" },
  resistance_break: { label: "저항돌파",   color: "#8b5cf6" },
  volume_breakout:  { label: "거래량돌파", color: "#3b82f6" },
  volume_surge:     { label: "거래량급등", color: "#f97316" },
  price_surge:      { label: "주가급등",   color: "#ec4899" },
};

function ScoreBar({ score }) {
  const max = 7;
  const pct = Math.round((score / max) * 100);
  const color = score >= 5 ? "#ef4444" : score >= 3 ? "#f59e0b" : "#6b7280";
  return (
    <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
      <div style={{
        width: 60, height: 6, background: "#374151", borderRadius: 3, overflow: "hidden"
      }}>
        <div style={{ width: `${pct}%`, height: "100%", background: color, borderRadius: 3 }} />
      </div>
      <span style={{ color, fontWeight: 700, fontSize: 13 }}>{score}/{max}</span>
    </div>
  );
}

function SignalBadges({ item }) {
  const active = Object.entries(SIGNAL_LABELS).filter(([key]) => item[key]);
  if (!active.length) return <span style={{ color: "#6b7280", fontSize: 11 }}>–</span>;
  return (
    <div style={{ display: "flex", flexWrap: "wrap", gap: 3 }}>
      {active.map(([key, { label, color }]) => (
        <span key={key} style={{
          background: color + "22", color, border: `1px solid ${color}55`,
          borderRadius: 4, padding: "1px 5px", fontSize: 10, whiteSpace: "nowrap",
        }}>
          {label}
        </span>
      ))}
    </div>
  );
}

function NextUpdate() {
  const now = new Date();
  const h = now.getHours();
  let next;
  if (h < 9)       next = "09:00";
  else if (h < 12) next = "12:00";
  else if (h < 15) next = "15:00";
  else              next = "내일 09:00";
  return <span style={{ color: "#6b7280", fontSize: 12 }}>다음 갱신: {next}</span>;
}

export default function ScreeningPage({ onSelect }) {
  const [data,        setData]        = useState(null);
  const [loading,     setLoading]     = useState(false);
  const [refreshing,  setRefreshing]  = useState(false);

  async function load() {
    setLoading(true);
    try {
      const res = await getScreening();
      setData(res.data);
    } catch (e) { console.error(e); }
    setLoading(false);
  }

  async function handleRefresh() {
    setRefreshing(true);
    try {
      await refreshScreening();
      await load();   // running=true 즉시 수신 → 자동 폴링이 이어받음
    } catch (e) {
      console.error(e);
    }
    setRefreshing(false);
  }

  useEffect(() => { load(); }, []);

  // 스크리너 실행 중일 때 3초마다 자동 재조회
  useEffect(() => {
    if (!data?.running) return;
    const timer = setInterval(() => { load(); }, 3000);
    return () => clearInterval(timer);
  }, [data?.running]);

  return (
    <div>
      <div className={s.toolbar}>
        <h2 className={s.pageTitle}>🔍 자동 종목 스크리닝</h2>
        <div style={{ display: "flex", alignItems: "center", gap: 10, marginLeft: "auto" }}>
          {data?.updated_at && (
            <span className={s.updated}>마지막 갱신: {data.updated_at}</span>
          )}
          <NextUpdate />
          <button
            className={s.refreshBtn}
            onClick={load}
            disabled={loading}
          >
            ↻ 갱신 확인
          </button>
          <button
            className={s.refreshBtn}
            onClick={handleRefresh}
            disabled={refreshing || data?.running}
            style={{ background: "#7c3aed" }}
          >
            {refreshing || data?.running ? "분석 중..." : "⚡ 즉시 재분석"}
          </button>
        </div>
      </div>

      {/* 상태 메시지 */}
      {data?.message && (
        <div className={s.loading}>{data.message}</div>
      )}
      {(loading) && !data && (
        <div className={s.loading}>캐시 확인 중...</div>
      )}
      {data?.running && !data?.message && (
        <div className={s.loading}>스크리닝 실행 중... (시총 상위 100종목 분석)</div>
      )}

      {/* 결과 없음 */}
      {data && !data.running && data.screened?.length === 0 && !data.message && (
        <div className={s.empty}>
          아직 스크리닝 결과가 없습니다.<br />
          ⚡ 즉시 재분석 버튼을 눌러 시작하세요.
        </div>
      )}

      {/* 결과 테이블 */}
      {data?.screened?.length > 0 && (
        <>
          <div style={{ padding: "8px 0 4px", color: "#9ca3af", fontSize: 12 }}>
            KOSPI 시가총액 상위 {data.total_scanned}개 분석 → 기술점수 상위 {data.screened.length}개
          </div>
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
                <th></th>
              </tr>
            </thead>
            <tbody>
              {data.screened.map((item, i) => (
                <tr
                  key={item.code}
                  className={s.clickableRow}
                  onClick={() => onSelect?.(item.code)}
                >
                  <td className={s.muted}>{i + 1}</td>
                  <td className={s.name}>
                    {typeof item.name === "string" ? item.name : item.code}
                    <span className={s.muted} style={{ marginLeft: 6, fontSize: 11 }}>
                      {item.code}
                    </span>
                  </td>
                  <td>{item.price?.toLocaleString()}원</td>
                  <td className={item.change_pct >= 0 ? s.up : s.down}>
                    {item.change_pct >= 0 ? "▲" : "▼"} {Math.abs(item.change_pct).toFixed(2)}%
                  </td>
                  <td className={item.volume_ratio >= 3 ? s.up : ""}>
                    {item.volume_ratio?.toFixed(1)}배
                  </td>
                  <td><ScoreBar score={item.total_score ?? 0} /></td>
                  <td><SignalBadges item={item} /></td>
                  <td>
                    <button className={s.smallBtn}>차트 →</button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </>
      )}

      {data?.error && <div className={s.error}>{data.error}</div>}
    </div>
  );
}
