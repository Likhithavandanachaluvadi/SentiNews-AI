'use client';

import React, { useEffect, useState } from 'react';
import {
  AreaChart,
  Area,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
} from 'recharts';

interface PriceData {
  date: string;
  close: number;
  volume: number;
}

interface StockChartProps {
  ticker: string;
  data?: PriceData[];
  isLoading?: boolean;
}

export default function StockChart({ ticker, data = [], isLoading = false }: StockChartProps) {
  const [chartData, setChartData] = useState<PriceData[]>([]);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (data && data.length > 0) {
      setChartData(data);
    }
  }, [data]);

  useEffect(() => {
    if (!ticker || (data && data.length > 0)) return;
    fetchPriceHistory(ticker);
  }, [ticker]);

  const fetchPriceHistory = async (tickerSymbol: string) => {
    try {
      const response = await fetch(`http://localhost:/api/v1/market/history/${tickerSymbol}`);
      if (!response.ok) {
        throw new Error('Failed to fetch price history');
      }
      const jsonData = await response.json();
      setChartData(jsonData.history || []);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Unknown error');
      console.error('Failed to fetch price history:', err);
    }
  };

  if (isLoading) {
    return (
      <div className="bg-card border border-border rounded-2xl shadow-xl">
        <div className="p-5 border-b border-border/60">
          <h3 className="text-lg font-bold text-foreground">Price History</h3>
          <p className="text-xs text-text-secondary">{ticker} - Last 30 Days</p>
        </div>
        <div className="p-5 h-80 flex items-center justify-center bg-background/50">
          <p className="text-text-secondary text-sm">Loading chart...</p>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="bg-card border border-border rounded-2xl shadow-xl">
        <div className="p-5 border-b border-border/60">
          <h3 className="text-lg font-bold text-foreground">Price History</h3>
          <p className="text-xs text-text-secondary">{ticker} - Last 30 Days</p>
        </div>
        <div className="p-5 h-80 flex items-center justify-center">
          <p className="text-bear-red text-sm font-semibold">{error}</p>
        </div>
      </div>
    );
  }

  if (!chartData || chartData.length === 0) {
    return (
      <div className="bg-card border border-border rounded-2xl shadow-xl">
        <div className="p-5 border-b border-border/60">
          <h3 className="text-lg font-bold text-foreground">Price History</h3>
          <p className="text-xs text-text-secondary">{ticker} - Last 30 Days</p>
        </div>
        <div className="p-5 h-80 flex items-center justify-center">
          <p className="text-text-secondary text-sm">No price data available</p>
        </div>
      </div>
    );
  }

  // Calculate min and max for Y-axis domain
  const prices = chartData.map(d => d.close);
  const minPrice = Math.min(...prices);
  const maxPrice = Math.max(...prices);
  const padding = (maxPrice - minPrice) * 0.1;

  return (
    <div className="bg-card border border-border rounded-2xl shadow-xl">
      <div className="p-5 border-b border-border/60">
        <h3 className="text-lg font-bold text-foreground">Price History</h3>
        <p className="text-xs text-text-secondary">{ticker} - Last 30 Days</p>
      </div>
      <div className="p-5">
        <div className="h-[300px] w-full">
          <ResponsiveContainer width="100%" height="100%">
            <AreaChart data={chartData} margin={{ top: 10, right: 30, left: 0, bottom: 0 }}>
              <defs>
                <linearGradient id="colorPrice" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="5%" stopColor="#3b82f6" stopOpacity={0.8} />
                  <stop offset="95%" stopColor="#3b82f6" stopOpacity={0} />
                </linearGradient>
              </defs>
              <CartesianGrid strokeDasharray="3 3" stroke="#1E293B" />
              <XAxis
                dataKey="date"
                tick={{ fontSize: 12, fill: '#94A3B8' }}
                interval={Math.floor(chartData.length / 6)}
                stroke="#1E293B"
              />
              <YAxis
                domain={[minPrice - padding, maxPrice + padding]}
                tick={{ fontSize: 12, fill: '#94A3B8' }}
                stroke="#1E293B"
              />
              <Tooltip
                contentStyle={{ backgroundColor: '#121A2B', borderColor: '#1E293B', borderRadius: '12px' }}
                formatter={(value) =>
                  typeof value === 'number' ? [`₹${value.toFixed(2)}`, 'Price'] : [value, 'Price']
                }
                labelFormatter={(label) => `Date: ${label}`}
              />
              <Area
                type="monotone"
                dataKey="close"
                stroke="#3b82f6"
                fillOpacity={1}
                fill="url(#colorPrice)"
              />
            </AreaChart>
          </ResponsiveContainer>
        </div>

        {/* Price Statistics */}
        <div className="grid grid-cols-3 gap-4 mt-6">
          <div className="bg-background/80 border border-border p-3 rounded-xl">
            <p className="text-xs text-text-secondary">Current Price</p>
            <p className="text-base font-bold text-foreground">
              ₹{chartData[chartData.length - 1].close.toFixed(2)}
            </p>
          </div>
          <div className="bg-background/80 border border-border p-3 rounded-xl">
            <p className="text-xs text-text-secondary">30-Day High</p>
            <p className="text-base font-bold text-bull-green">
              ₹{maxPrice.toFixed(2)}
            </p>
          </div>
          <div className="bg-background/80 border border-border p-3 rounded-xl">
            <p className="text-xs text-text-secondary">30-Day Low</p>
            <p className="text-base font-bold text-bear-red">
              ₹{minPrice.toFixed(2)}
            </p>
          </div>
        </div>
      </div>
    </div>
  );
}
