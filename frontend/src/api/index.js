import axios from "axios";

const api = axios.create({ baseURL: "/api/dashboard" });

export const getWatchlist  = ()              => api.get("/watchlist");
export const getChart      = (code, days=60) => api.get(`/chart/${code}?days=${days}`);
export const getFinancial  = (code)          => api.get(`/financial/${code}`);
export const getSentiment  = (code, hours=6) => api.get(`/sentiment/${code}?hours=${hours}`);
export const getScreening     = ()  => api.get("/screening");
export const refreshScreening = ()  => api.post("/screening/refresh");

// 감시 종목 관리 (/watch 엔드포인트)
export const getWatchCodes   = ()     => axios.get("/watch");
export const addWatchCode    = (code) => axios.post(`/watch/${code}`);
export const removeWatchCode = (code) => axios.delete(`/watch/${code}`);

// 백테스트
export const getBacktest = (code, start, end, strategy = "hold", holdDays = 20, takeProfit = 10, stopLoss = 5) =>
  api.get(`/backtest/${code}`, { params: { start, end, strategy, hold_days: holdDays, take_profit: takeProfit, stop_loss: stopLoss } });
