import { useState, useRef } from "react";
import { getBacktest } from "../api";
import s from "./BacktestModal.module.css";

const TODAY    = new Date().toISOString().split("T")[0];
const ONE_YEAR = new Date(Date.now() - 365 * 24 * 3600 * 1000).toISOString().split("T")[0];

const retColor = (v) => (v > 0 ? "var(--green)" : v < 0 ? "var(--red)" : "var(--muted)");
const fmtPct   = (v) => (v >= 0 ? `+${v.toFixed(1)}%` : `${v.toFixed(1)}%`);
const fmtPrice = (v) => `${Number(v).toLocaleString()}원`;

/* ── 지표 카드 ───────────────────────────────────────── */
function Metric({ label, value, valueColor, sub }) {
  return (
    <div className={s.metricCard}>
      <div className={s.metricLabel}>{label}</div>
      <div className={s.metricValue} style={{ color: valueColor }}>{value}</div>
      {sub && <div className={s.metricSub}>{sub}</div>}
    </div>
  );
}

/* ── 수익률 스파크라인 ────────────────────────────────── */
function Sparkline({ data }) {
  if (!data || data.length < 2) return null;
  const vals  = data.map((d) => d.pct);
  const min   = Math.min(...vals, 0);
  const max   = Math.max(...vals, 0);
  const range = max - min || 1;
  const W = 400, H = 52;
  const pts = vals
    .map((v, i) => `${(i / (vals.length - 1)) * W},${H - ((v - min) / range) * H}`)
    .join(" ");
  const zeroY    = H - ((0 - min) / range) * H;
  const lastColor = vals[vals.length - 1] >= 0 ? "#10b981" : "#ef4444";
  return (
    <svg viewBox={`0 0 ${W} ${H}`} className={s.spark} preserveAspectRatio="none">
      <line x1="0" y1={zeroY} x2={W} y2={zeroY}
        stroke="var(--border)" strokeWidth="0.8" strokeDasharray="3,3" />
      <polyline points={pts} fill="none"
        stroke={lastColor} strokeWidth="1.8" strokeLinejoin="round" />
    </svg>
  );
}

/* ── 날짜 유틸 ───────────────────────────────────────── */
function addMonths(dateStr, months) {
  const d = new Date(dateStr);
  d.setMonth(d.getMonth() + months);
  return `${d.getFullYear()}.${String(d.getMonth() + 1).padStart(2, "0")}.${String(d.getDate()).padStart(2, "0")}`;
}

/* ── 시나리오 예측 테이블 (단순 보유) ────────────────── */
function ProjectionTable({ projections, currentPrice, currentDate, targetDate }) {
  const rows = [
    { label: "1개월", key: "1m",  until: currentDate ? addMonths(currentDate, 1)  : null },
    { label: "3개월", key: "3m",  until: currentDate ? addMonths(currentDate, 3)  : null },
    { label: "6개월", key: "6m",  until: currentDate ? addMonths(currentDate, 6)  : null },
    { label: "1년",   key: "1y",  until: currentDate ? addMonths(currentDate, 12) : null },
  ];
  if (projections?.target && targetDate) {
    const [y, m, d] = targetDate.split("-");
    rows.push({ label: `${y}.${m}.${d}`, key: "target", isTarget: true });
  }
  const cols = [
    { key: "bull",  label: "낙관 (+1σ)", headerColor: "var(--green)" },
    { key: "base",  label: "기본 (평균)", headerColor: "var(--text)" },
    { key: "bear",  label: "비관 (−1σ)", headerColor: "#f59e0b" },
    { key: "worst", label: "최악 (MDD)", headerColor: "var(--red)" },
  ];
  const refDate = currentDate ? currentDate.replaceAll("-", ".") : null;
  return (
    <div className={s.projWrap}>
      <div className={s.projTitle}>현재가 기준 시나리오 예측</div>
      <div className={s.projSubtitle}>
        기준 시점: <strong>{refDate}</strong> 종가 {fmtPrice(currentPrice)} — 이 날짜부터 각 기간이 지난 시점의 예상 가격
      </div>
      <div className={s.projTableWrap}>
        <table className={s.projTable}>
          <thead>
            <tr>
              <th>기간 (도달일)</th>
              {cols.map((c) => (
                <th key={c.key} style={{ color: c.headerColor }}>{c.label}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {rows.map(({ label, key, isTarget, until }) => {
              const p = projections[key];
              if (!p) return null;
              return (
                <tr key={key} style={isTarget ? {
                  background: "rgba(99,102,241,0.08)",
                  borderTop: "2px solid rgba(99,102,241,0.35)",
                } : {}}>
                  <td className={s.projPeriod}>
                    {isTarget
                      ? <span style={{ color: "#6366f1", fontWeight: 700 }}>★ {label}</span>
                      : (<>
                          <div>{label}</div>
                          {until && <div style={{ fontSize: 10, color: "var(--muted)", fontWeight: 400, marginTop: 2 }}>~{until}</div>}
                        </>)}
                  </td>
                  {cols.map((c) => (
                    <td key={c.key} className={s.projCell}>
                      <div style={{
                        color: retColor(p[`${c.key}_pct`]),
                        fontWeight: isTarget ? 700 : 600,
                        fontSize: isTarget ? 14 : 13,
                      }}>
                        {fmtPct(p[`${c.key}_pct`])}
                      </div>
                      <div className={s.projPrice}>{fmtPrice(p[`${c.key}_price`])}</div>
                    </td>
                  ))}
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
      <div className={s.projNote}>
        낙관/비관: 연환산수익률 ± 연간변동성(1σ) 적용 · 최악: 분석기간 최대낙폭(MDD) 기간 비례 적용
        {targetDate && " · ★ 목표일 = 현재가 기준 해당 기간 복리 추정"}
      </div>
    </div>
  );
}

/* ── 시그널 진입 예측 카드 ───────────────────────────── */
function SignalProjectionCard({ projection, currentPrice }) {
  const cols = [
    { key: "bull",  label: "낙관 (+1σ)", color: "var(--green)" },
    { key: "base",  label: "기본 (평균)", color: "var(--text)" },
    { key: "bear",  label: "비관 (−1σ)", color: "#f59e0b" },
    { key: "worst", label: "최악 (최대손실)", color: "var(--red)" },
  ];
  return (
    <div className={s.projWrap}>
      <div className={s.projTitle}>다음 시그널 진입 예측</div>
      <div className={s.projSubtitle}>
        진입 시점: 시그널 발생 다음 거래일 <strong>시가</strong>에 매수
        {" · "}청산 시점: 익절·손절 도달 또는 최대 <strong>{projection.hold_days}거래일</strong> 후 종가
      </div>
      <div className={s.projSubtitle} style={{ marginTop: 2 }}>
        예측 기준가: {fmtPrice(currentPrice)} (현재가) · 과거 {projection.sample_count}건 실거래 통계 기반
      </div>
      <div className={s.projTableWrap}>
        <table className={s.projTable}>
          <thead>
            <tr>
              {cols.map((c) => (
                <th key={c.key} style={{ color: c.color }}>{c.label}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            <tr>
              {cols.map((c) => (
                <td key={c.key} className={s.projCell}>
                  <div style={{ color: retColor(projection[`${c.key}_pct`]), fontWeight: 600, fontSize: 13 }}>
                    {fmtPct(projection[`${c.key}_pct`])}
                  </div>
                  <div className={s.projPrice}>{fmtPrice(projection[`${c.key}_price`])}</div>
                </td>
              ))}
            </tr>
          </tbody>
        </table>
      </div>
      <div className={s.projNote}>
        수익률 = 청산가 ÷ 진입 시가 − 1 · 낙관/비관: 과거 거래 평균 ± 표준편차(1σ) · 최악: 과거 최대 단일 손실
      </div>
    </div>
  );
}

/* ── 메인 ────────────────────────────────────────────── */
export default function BacktestModal({ code, name, onClose }) {
  const [start,      setStart]      = useState(ONE_YEAR);
  const [end,        setEnd]        = useState(TODAY);
  const [strategy,   setStrategy]   = useState("hold");
  const [holdDays,   setHoldDays]   = useState(20);
  const [takeProfit, setTakeProfit] = useState(10);
  const [stopLoss,   setStopLoss]   = useState(5);
  const [loading,    setLoading]    = useState(false);
  const [result,     setResult]     = useState(null);
  const [error,      setError]      = useState("");

  const isFutureMode = end > TODAY;

  const stratAnchorRef                  = useRef(null);
  const [stratTipPos, setStratTipPos]   = useState(null);

  function showStratTip() {
    if (!stratAnchorRef.current) return;
    const r = stratAnchorRef.current.getBoundingClientRect();
    const tipH = 220;
    const below = r.bottom + 10;
    const above = r.top - tipH - 10;
    setStratTipPos({
      left: r.left,
      top:  below + tipH < window.innerHeight ? below : Math.max(above, 8),
    });
  }
  function hideStratTip() { setStratTipPos(null); }

  async function handleRun() {
    if (!start || !end || start >= end) { setError("올바른 날짜 범위를 입력하세요."); return; }
    setLoading(true); setError(""); setResult(null);
    try {
      const r = await getBacktest(
        code, start.replace(/-/g, ""), end.replace(/-/g, ""),
        strategy, holdDays, takeProfit, stopLoss,
      );
      if (r.data.error) setError(r.data.error);
      else              setResult(r.data);
    } catch {
      setError("백테스트 실행 중 오류가 발생했습니다.");
    }
    setLoading(false);
  }

  const stratTooltip = (
    <div className={s.tooltipFixed} style={stratTipPos
      ? { top: stratTipPos.top, left: stratTipPos.left }
      : { display: "none" }
    }>
      <div className={s.tooltipHeading}>전략 선택 안내</div>
      <div className={s.tooltipBlock}>
        <div className={s.tooltipBlockTitle}>📈 단순 보유</div>
        <div className={s.tooltipDesc}>
          학습 기간의 연환산 수익률·변동성·MDD를 현재가에 투영해
          1개월~1년 시나리오 가격을 계산합니다.
          종목의 장기 특성 파악에 적합합니다.
        </div>
      </div>
      <div className={s.tooltipBlock}>
        <div className={s.tooltipBlockTitle}>⚡ 시그널 진입</div>
        <div className={s.tooltipDesc}>
          거래량 3배 + 주가 5% 급등이 동시에 충족된 날을
          진입 시점으로 보고, 과거 실제 거래 성과를 검증합니다.
          단기 트레이딩 전략 검증에 적합합니다.
        </div>
        <div className={s.tooltipBullets}>
          <span>• 최대 보유: 10~20거래일 권장</span>
          <span>• 익절 8~15% / 손절 4~7% 조합이 일반적</span>
          <span>• 거래 5건 이상이어야 통계 유효</span>
        </div>
      </div>
    </div>
  );

  return (
    <div className={s.overlay} onClick={(e) => e.target === e.currentTarget && onClose()}>
      <div className={s.modal}>
        {stratTooltip}

        {/* 헤더 */}
        <div className={s.header}>
          <div className={s.headerLeft}>
            <span className={s.title}>📊 백테스트</span>
            <span className={s.subtitle}>
              {name ?? code}
              <span className={s.codeTag}>{code}</span>
            </span>
          </div>
          <button className={s.closeBtn} onClick={onClose}>×</button>
        </div>

        <div className={s.body}>

          {/* 설정 */}
          <div className={s.settingsBox}>
            <div className={s.settingsRow}>
              <label className={s.settingsLabel}>{isFutureMode ? "목표 기간" : "학습 기간"}</label>
              <div className={s.dateRange}>
                <input type="date" className={s.dateInput} value={start}
                  onChange={(e) => setStart(e.target.value)} max={end} />
                <span className={s.dateSep}>~</span>
                <input type="date" className={s.dateInput} value={end}
                  onChange={(e) => setEnd(e.target.value)} min={start} />
              </div>
              <span className={s.settingsHint}>
                {isFutureMode
                  ? "🔮 미래 예측 모드 — 최근 실제 데이터로 학습 후 목표일까지 시나리오를 산출합니다"
                  : "과거 이 기간의 패턴을 학습해 현재가 기준으로 예측합니다"}
              </span>
            </div>

            <div className={s.settingsRow}>
              <label className={s.settingsLabel}>
                <span
                  ref={stratAnchorRef}
                  className={s.tooltipAnchor}
                  onMouseEnter={showStratTip}
                  onMouseLeave={hideStratTip}
                >
                  전략
                </span>
              </label>
              <select className={s.select} value={strategy} onChange={(e) => setStrategy(e.target.value)}>
                <option value="hold">단순 보유 — 과거 수익률 패턴 기반 예측</option>
                <option value="signal">시그널 진입 — 거래량·주가 급등 신호 기반 검증</option>
              </select>
            </div>

            {strategy === "signal" && (
              <div className={s.signalOptions}>
                <div className={s.optRow}>
                  <span className={s.optLabel}>최대 보유</span>
                  <input type="number" className={s.numInput} value={holdDays} min={1} max={120}
                    onChange={(e) => setHoldDays(+e.target.value)} />
                  <span className={s.optUnit}>거래일</span>
                </div>
                <div className={s.optRow}>
                  <span className={s.optLabel}>익절</span>
                  <input type="number" className={s.numInput} value={takeProfit} min={1} max={50} step={0.5}
                    onChange={(e) => setTakeProfit(+e.target.value)} />
                  <span className={s.optUnit}>%</span>
                </div>
                <div className={s.optRow}>
                  <span className={s.optLabel}>손절</span>
                  <input type="number" className={s.numInput} value={stopLoss} min={1} max={30} step={0.5}
                    onChange={(e) => setStopLoss(+e.target.value)} />
                  <span className={s.optUnit}>%</span>
                </div>
              </div>
            )}

            <button className={s.runBtn} onClick={handleRun} disabled={loading}>
              {loading ? "⏳ 분석 중..." : "▶ 백테스트 시작"}
            </button>
          </div>

          {/* 오류 */}
          {error && <div className={s.errorBox}>{error}</div>}

          {/* 결과 */}
          {result && (
            <div className={s.results}>

              {/* 현재가 배지 */}
              <div className={s.currentPriceBadge}>
                <span className={s.cpLabel}>시뮬레이션 기준가 (현재가)</span>
                <span className={s.cpValue}>{fmtPrice(result.current_price)}</span>
                <span className={s.cpDate}>{result.current_date} 종가</span>
                {result.is_future_mode && (
                  <span style={{
                    marginLeft: 10,
                    fontSize: 11,
                    color: "#6366f1",
                    background: "rgba(99,102,241,0.1)",
                    borderRadius: 4,
                    padding: "2px 7px",
                    fontWeight: 600,
                  }}>
                    🔮 미래 예측 · 목표 {result.target_date}
                  </span>
                )}
              </div>

              {/* 패턴 학습 결과 */}
              <div className={s.sectionTitle}>
                {result.is_future_mode
                  ? `학습 데이터 (${result.hist_start} ~ ${result.hist_end} · ${result.hist_days}거래일)`
                  : `과거 패턴 분석 (${result.hist_start} ~ ${result.hist_end} · ${result.hist_days}거래일)`}
              </div>
              <div className={s.metrics}>
                <Metric
                  label={result.annual_return_note ? "기간 합산 수익률 ⚠" : "연환산 수익률"}
                  value={fmtPct(result.annual_return_pct)}
                  valueColor={retColor(result.annual_return_pct)}
                  sub={result.annual_return_note ?? `기간 합산 ${fmtPct(result.hist_total_return_pct)}`}
                />
                <Metric
                  label="연간 변동성 (1σ)"
                  value={`${result.annual_vol_pct.toFixed(1)}%`}
                  valueColor="var(--muted)"
                  sub="높을수록 가격 진폭 큼"
                />
                <Metric
                  label="최대 낙폭 (MDD)"
                  value={fmtPct(result.mdd_pct)}
                  valueColor="var(--red)"
                  sub="최고점 대비 최대 하락"
                />
                <Metric
                  label="샤프 비율"
                  value={result.sharpe.toFixed(2)}
                  valueColor={result.sharpe >= 1 ? "var(--green)" : result.sharpe >= 0 ? "var(--muted)" : "var(--red)"}
                  sub={result.sharpe >= 1 ? "우수" : result.sharpe >= 0 ? "보통" : "부진"}
                />
              </div>

              {/* 수익률 추이 */}
              {result.equity_curve?.length > 1 && (
                <div className={s.sparkWrap}>
                  <div className={s.sparkLabel}>학습 기간 수익률 추이</div>
                  <Sparkline data={result.equity_curve} />
                  <div className={s.sparkAxis}>
                    <span>{result.hist_start}</span>
                    <span>{result.hist_end}</span>
                  </div>
                </div>
              )}

              {/* 시나리오 예측 */}
              {result.strategy === "시그널 진입" && result.signal_projection ? (
                <SignalProjectionCard
                  projection={result.signal_projection}
                  currentPrice={result.current_price}
                />
              ) : (
                <ProjectionTable
                  projections={result.projections}
                  currentPrice={result.current_price}
                  currentDate={result.current_date}
                  targetDate={result.target_date}
                />
              )}

              {/* 시그널 전략 추가 정보 */}
              {result.strategy === "시그널 진입" && (
                <>
                  {/* 현재 시그널 상태 */}
                  <div className={result.signal_now ? s.signalOn : s.signalOff}>
                    {result.signal_now
                      ? "🚨 현재 시그널 발생 — 진입 조건(거래량 급등 + 주가 상승) 충족"
                      : "⏳ 현재 시그널 없음 — 진입 조건 미충족"}
                  </div>

                  {/* 과거 시그널 성과 */}
                  <div className={s.sectionTitle}>과거 시그널 성과 ({result.trade_count}건)</div>
                  {result.trade_count === 0 ? (
                    <div className={s.noTrades}>
                      학습 기간 내 시그널 조건을 충족하는 날이 없었습니다.
                    </div>
                  ) : (
                    <>
                      <div className={s.metrics}>
                        <Metric
                          label="총 거래 횟수"
                          value={`${result.trade_count}건`}
                        />
                        <Metric
                          label="승률"
                          value={`${result.win_rate.toFixed(1)}%`}
                          valueColor={result.win_rate >= 50 ? "var(--green)" : "var(--red)"}
                        />
                        <Metric
                          label="평균 수익률"
                          value={fmtPct(result.avg_return_pct)}
                          valueColor={retColor(result.avg_return_pct)}
                        />
                        <Metric
                          label="누적 수익률"
                          value={fmtPct(result.total_return_pct)}
                          valueColor={retColor(result.total_return_pct)}
                        />
                      </div>
                      <div className={s.tableWrap}>
                        <table className={s.tradeTable}>
                          <thead>
                            <tr>
                              <th>진입일</th><th>매수가</th>
                              <th>청산일</th><th>매도가</th>
                              <th>수익률</th><th>사유</th>
                            </tr>
                          </thead>
                          <tbody>
                            {result.trades.map((t, i) => (
                              <tr key={i} className={t.return_pct >= 0 ? s.winRow : s.lossRow}>
                                <td>{t.entry_date}</td>
                                <td>{t.entry_price.toLocaleString()}원</td>
                                <td>{t.exit_date}</td>
                                <td>{t.exit_price.toLocaleString()}원</td>
                                <td style={{ color: retColor(t.return_pct), fontWeight: 700 }}>
                                  {fmtPct(t.return_pct)}
                                </td>
                                <td className={s.exitReason}>{t.exit_reason}</td>
                              </tr>
                            ))}
                          </tbody>
                        </table>
                      </div>
                    </>
                  )}
                </>
              )}

              <div className={s.disclaimer}>
                ⚠️ 과거 패턴 기반 통계적 추정값입니다. 실제 미래 수익을 보장하지 않으며
                투자 판단의 참고 자료로만 활용하세요.
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
