import { useEffect, useState } from "react";
import { getFinancial, getWatchlist } from "../api";
import { RadarChart, Radar, PolarGrid, PolarAngleAxis, ResponsiveContainer } from "recharts";
import s from "./Page.module.css";

export default function FinancialPage({ code: initCode }) {
  const [codes,   setCodes]   = useState([]);
  const [code,    setCode]    = useState(initCode || null);
  const [data,    setData]    = useState(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    getWatchlist().then(res => {
      const list = res.data.watchlist.map(w => ({ code: w.code, name: w.name }));
      setCodes(list);
      if (!code && list.length > 0) setCode(list[0].code);
    });
  }, []);

  useEffect(() => {
    if (!code) return;
    setLoading(true);
    getFinancial(code).then(res => { setData(res.data); setLoading(false); });
  }, [code]);

  const metrics = data ? [
    { label: "PER",     value: data.per,       unit: "배",  good: v => v > 0 && v < 15 },
    { label: "PBR",     value: data.pbr,       unit: "배",  good: v => v > 0 && v < 1.5 },
    { label: "ROE",     value: data.roe,       unit: "%",   good: v => v > 10 },
    { label: "EPS",     value: data.eps,       unit: "원",  good: v => v > 0 },
    { label: "배당수익률", value: data.div_yield, unit: "%", good: v => v > 2 },
    { label: "시가총액", value: data.market_cap_trillion, unit: "조", good: () => true },
  ] : [];

  const radarData = data ? [
    { subject: "PER",  value: Math.min(100, Math.max(0, 100 - data.per * 3)) },
    { subject: "PBR",  value: Math.min(100, Math.max(0, 100 - data.pbr * 20)) },
    { subject: "ROE",  value: Math.min(100, data.roe * 3) },
    { subject: "배당",  value: Math.min(100, data.div_yield * 20) },
    { subject: "EPS",  value: data.eps > 0 ? 70 : 30 },
  ] : [];

  return (
    <div>
      <div className={s.toolbar}>
        <h2 className={s.pageTitle}>💰 재무제표</h2>
        <select className={s.select} value={code || ""} onChange={e => setCode(e.target.value)}>
          {codes.map(c => <option key={c.code} value={c.code}>{c.name} ({c.code})</option>)}
        </select>
      </div>

      {loading && <div className={s.loading}>불러오는 중...</div>}

      {data && !data.error && (
        <div className={s.twoCol}>
          {/* 지표 카드 */}
          <div className={s.grid3}>
            {metrics.map(m => (
              <div key={m.label} className={s.card}>
                <div className={s.metricLabel}>{m.label}</div>
                <div className={`${s.metricValue} ${m.good(m.value) ? s.good : s.neutral}`}>
                  {typeof m.value === "number" ? m.value.toLocaleString() : "-"} {m.unit}
                </div>
              </div>
            ))}
          </div>

          {/* 레이더 차트 */}
          <div className={s.card}>
            <div className={s.cardTitle}>종합 평가</div>
            <ResponsiveContainer width="100%" height={240}>
              <RadarChart data={radarData}>
                <PolarGrid stroke="#2e3254" />
                <PolarAngleAxis dataKey="subject" tick={{ fill: "#8890b0", fontSize: 12 }} />
                <Radar dataKey="value" stroke="#7c6cf0" fill="#7c6cf0" fillOpacity={0.3} />
              </RadarChart>
            </ResponsiveContainer>
          </div>
        </div>
      )}

      {data?.error && <div className={s.error}>{data.error}</div>}
    </div>
  );
}
