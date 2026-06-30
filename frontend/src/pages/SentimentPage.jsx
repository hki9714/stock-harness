import { useEffect, useState } from "react";
import { getSentiment, getWatchlist } from "../api";
import { PieChart, Pie, Cell, ResponsiveContainer, Tooltip } from "recharts";
import s from "./Page.module.css";

const HOURS = [1, 3, 6, 12, 24];

export default function SentimentPage({ code: initCode }) {
  const [codes,   setCodes]   = useState([]);
  const [code,    setCode]    = useState(initCode || null);
  const [hours,   setHours]   = useState(6);
  const [data,    setData]    = useState(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (initCode && initCode !== code) setCode(initCode);
  }, [initCode]);

  useEffect(() => {
    getWatchlist().then(res => {
      const list = (res.data?.watchlist ?? []).map(w => ({
        code: w.code,
        name: typeof w.name === "string" ? w.name : w.code,
      }));
      setCodes(list);
      setCode(cur => (!cur && list.length > 0) ? list[0].code : cur);
    }).catch(() => {});
  }, []);

  useEffect(() => {
    if (!code) return;
    setLoading(true);
    getSentiment(code, hours)
      .then(res => { setData(res.data); setLoading(false); })
      .catch(() => setLoading(false));
  }, [code, hours]);

  const pieData = data ? [
    { name: "긍정", value: data.positive_count, color: "#3dd68c" },
    { name: "부정", value: data.negative_count, color: "#f06464" },
  ] : [];

  const sentimentColor = {
    "긍정": s.up, "부정": s.down, "중립": s.neutral
  };

  return (
    <div>
      <div className={s.toolbar}>
        <h2 className={s.pageTitle}>💬 감성 분석</h2>
        <select className={s.select} value={code || ""} onChange={e => setCode(e.target.value)}>
          {codes.map(c => <option key={c.code} value={c.code}>{c.name} ({c.code})</option>)}
        </select>
        <div className={s.btnGroup}>
          {HOURS.map(h => (
            <button
              key={h}
              className={`${s.periodBtn} ${hours === h ? s.active : ""}`}
              onClick={() => setHours(h)}
            >
              {h}시간
            </button>
          ))}
        </div>
      </div>

      {loading && <div className={s.loading}>분석 중...</div>}

      {data && !data.error && (
        <div className={s.twoCol}>
          {/* 좌측: 수치 + 파이 */}
          <div>
            <div className={s.grid3} style={{ marginBottom: 16 }}>
              <div className={s.card}>
                <div className={s.metricLabel}>전체 게시글</div>
                <div className={s.metricValue}>{data.total_count}건</div>
              </div>
              <div className={s.card}>
                <div className={s.metricLabel}>긍정</div>
                <div className={`${s.metricValue} ${s.up}`}>{data.positive_count}건</div>
              </div>
              <div className={s.card}>
                <div className={s.metricLabel}>종합 감성</div>
                <div className={`${s.metricValue} ${sentimentColor[data.sentiment]}`}>
                  {data.sentiment}
                </div>
              </div>
            </div>

            <div className={s.card}>
              <div className={s.cardTitle}>긍정 / 부정 비율</div>
              <ResponsiveContainer width="100%" height={200}>
                <PieChart>
                  <Pie data={pieData} dataKey="value" cx="50%" cy="50%" outerRadius={80} label={({name,percent})=>`${name} ${(percent*100).toFixed(0)}%`}>
                    {pieData.map((entry, i) => <Cell key={i} fill={entry.color} />)}
                  </Pie>
                  <Tooltip />
                </PieChart>
              </ResponsiveContainer>
            </div>
          </div>

          {/* 우측: 최근 게시글 */}
          <div className={s.card}>
            <div className={s.cardTitle}>최근 게시글 ({hours}시간)</div>
            <div className={s.postList}>
              {data.recent_posts.length === 0
                ? <div className={s.muted}>게시글 없음</div>
                : data.recent_posts.map((p, i) => (
                  <div key={i} className={s.postItem}>
                    <span className={s.postTime}>{p.datetime}</span>
                    <span className={s.postTitle}>{p.title}</span>
                  </div>
                ))
              }
            </div>
          </div>
        </div>
      )}

      {data?.error && <div className={s.error}>{data.error}</div>}
    </div>
  );
}
