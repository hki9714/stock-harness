import { useEffect, useRef, useState } from "react";
import { createChart }  from "lightweight-charts";
import { getChart }     from "../api";
import { getWatchlist } from "../api";
import s from "./Page.module.css";

const PERIODS = [
  { label: "1개월", days: 30 },
  { label: "3개월", days: 60 },
  { label: "6개월", days: 120 },
  { label: "1년",   days: 240 },
];

function safeName(raw, fallback) {
  return typeof raw === "string" && raw ? raw : fallback;
}

// codes 배열에 항목 추가 (이미 있으면 스킵, 없으면 앞에 추가)
function mergeCodes(prev, incoming) {
  const incomingMap = new Map(incoming.map(c => [c.code, c]));
  const extras = prev.filter(c => !incomingMap.has(c.code));
  return [...extras, ...incoming];
}

export default function ChartPage({ code: initCode }) {
  const [codes,   setCodes]   = useState([]);
  const [code,    setCode]    = useState(initCode || null);
  const [days,    setDays]    = useState(60);
  const [data,    setData]    = useState(null);
  const [loading, setLoading] = useState(false);

  const chartRef = useRef(null);
  const rsiRef   = useRef(null);
  const chartObj = useRef(null);
  const rsiObj   = useRef(null);

  // initCode prop이 바뀌면 code 상태 동기화 (이미 마운트된 상태에서 다른 종목 클릭 시)
  useEffect(() => {
    if (initCode && initCode !== code) setCode(initCode);
  }, [initCode]);

  // 감시 종목 목록 (race condition 방지: 기존 extra 종목 보존)
  useEffect(() => {
    getWatchlist().then(res => {
      const list = (res.data?.watchlist ?? []).map(w => ({
        code: w.code,
        name: safeName(w.name, w.code),
      }));
      setCodes(prev => mergeCodes(prev, list));
      // code가 없을 때만 감시 목록 첫 번째로 초기화
      setCode(cur => (!cur && list.length > 0) ? list[0].code : cur);
    }).catch(() => {});
  }, []);

  // 차트 데이터 로드
  useEffect(() => {
    if (!code) return;
    setLoading(true);
    setData(null);
    getChart(code, days).then(res => {
      const d = res.data;
      setData(d);
      setLoading(false);
      // 감시 목록에 없는 종목(스크리닝 등)도 드롭다운에 추가
      if (d?.code) {
        const entry = { code: d.code, name: safeName(d.name, d.code) };
        setCodes(prev => prev.some(c => c.code === d.code) ? prev : [entry, ...prev]);
      }
    }).catch(() => setLoading(false));
  }, [code, days]);

  // 차트 렌더
  useEffect(() => {
    if (!data || !chartRef.current || !rsiRef.current) return;
    if (data.error) return;

    chartObj.current?.remove();
    rsiObj.current?.remove();

    const OPTS = {
      layout:     { background: { color: "#1a1d2e" }, textColor: "#8890b0" },
      grid:       { vertLines: { color: "#2e3254" }, horzLines: { color: "#2e3254" } },
      crosshair:  { mode: 1 },
      rightPriceScale: { borderColor: "#2e3254" },
      timeScale:  { borderColor: "#2e3254", timeVisible: true },
    };

    const chart = createChart(chartRef.current, { ...OPTS, height: 360 });
    chartObj.current = chart;

    const candle = chart.addCandlestickSeries({
      upColor: "#3dd68c", downColor: "#f06464",
      wickUpColor: "#3dd68c", wickDownColor: "#f06464",
      borderVisible: false,
    });
    candle.setData(data.candles);

    const ma5Line  = chart.addLineSeries({ color: "#f0a840", lineWidth: 1, title: "MA5" });
    const ma20Line = chart.addLineSeries({ color: "#5b8af0", lineWidth: 1, title: "MA20" });
    const ma60Line = chart.addLineSeries({ color: "#7c6cf0", lineWidth: 1, title: "MA60" });
    ma5Line.setData(data.ma5);
    ma20Line.setData(data.ma20);
    ma60Line.setData(data.ma60);

    const volSeries = chart.addHistogramSeries({
      color: "#2e3254", priceFormat: { type: "volume" },
      priceScaleId: "volume",
    });
    chart.priceScale("volume").applyOptions({ scaleMargins: { top: 0.8, bottom: 0 } });
    volSeries.setData(data.candles.map(c => ({
      time:  c.time,
      value: c.volume,
      color: c.close >= c.open ? "#3dd68c44" : "#f0646444",
    })));

    const rsi = createChart(rsiRef.current, { ...OPTS, height: 120 });
    rsiObj.current = rsi;
    const rsiLine = rsi.addLineSeries({ color: "#f0a840", lineWidth: 1, title: "RSI" });
    rsiLine.setData(data.rsi);

    [70, 30].forEach(v => {
      rsi.addLineSeries({
        color: v === 70 ? "#f0646466" : "#3dd68c66",
        lineWidth: 1, lineStyle: 2,
      }).setData(data.rsi.map(r => ({ time: r.time, value: v })));
    });

    chart.timeScale().fitContent();
    rsi.timeScale().fitContent();

    chart.timeScale().subscribeVisibleLogicalRangeChange(range => {
      if (range) rsi.timeScale().setVisibleLogicalRange(range);
    });

  }, [data]);

  const displayName = safeName(data?.name, code);

  return (
    <div>
      <div className={s.toolbar}>
        <h2 className={s.pageTitle}>📈 차트 분석</h2>
        <select className={s.select} value={code || ""} onChange={e => setCode(e.target.value)}>
          {codes.map(c => (
            <option key={c.code} value={c.code}>{c.name} ({c.code})</option>
          ))}
          {/* 선택된 코드가 목록에 없을 때 임시 옵션 표시 */}
          {code && !codes.some(c => c.code === code) && (
            <option value={code}>{code}</option>
          )}
        </select>
        <div className={s.btnGroup}>
          {PERIODS.map(p => (
            <button
              key={p.days}
              className={`${s.periodBtn} ${days === p.days ? s.active : ""}`}
              onClick={() => setDays(p.days)}
            >
              {p.label}
            </button>
          ))}
        </div>
      </div>

      {loading && <div className={s.loading}>차트 로딩 중...</div>}

      {data?.error && <div className={s.error}>{data.error}</div>}

      {!loading && data && !data.error && (
        <div className={s.chartWrap}>
          <div className={s.chartTitle}>{displayName} ({data.code})</div>
          <div ref={chartRef} />
          <div className={s.rsiLabel}>RSI (14)</div>
          <div ref={rsiRef} />
        </div>
      )}
    </div>
  );
}
