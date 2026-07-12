'use client';

import React from 'react';
import { RadialBarChart, RadialBar, PolarAngleAxis, Legend, ResponsiveContainer } from 'recharts';

interface SentimentMeterProps {
  bullScore: number; // 0-100
  bearScore: number; // 0-100
  sentimentScore?: number; // -100 to +100
  isLoading?: boolean;
}

export default function SentimentMeter({
  bullScore = 0,
  bearScore = 0,
  sentimentScore = 0,
  isLoading = false,
}: SentimentMeterProps) {
  // Normalize scores for data viz
  const totalScore = bullScore + bearScore || 1; // Prevent division by zero
  const bullPercentage = (bullScore / totalScore) * 100;
  const bearPercentage = (bearScore / totalScore) * 100;

  // Determine sentiment direction
  const isBullish = sentimentScore > 25;
  const isBearish = sentimentScore < -25;
  const isNeutral = !isBullish && !isBearish;

  const sentimentLabel = isBullish ? 'Bullish' : isBearish ? 'Bearish' : 'Neutral';
  const sentimentColor = isBullish ? 'text-bull-green' : isBearish ? 'text-bear-red' : 'text-gold-accent';

  // Gauge data
  const data = [
    {
      name: 'Bull',
      value: bullPercentage,
      fill: '#00C896', // Green
    },
    {
      name: 'Bear',
      value: bearPercentage,
      fill: '#FF5A5F', // Red
    },
  ];

  if (isLoading) {
    return (
      <div className="bg-card border border-border rounded-2xl shadow-xl">
        <div className="p-5 border-b border-border/60">
          <h3 className="text-lg font-bold text-foreground">Market Sentiment</h3>
          <p className="text-xs text-text-secondary">Bull vs Bear Analysis</p>
        </div>
        <div className="p-5 h-64 flex items-center justify-center bg-background/50">
          <p className="text-text-secondary text-sm">Loading sentiment analysis...</p>
        </div>
      </div>
    );
  }

  return (
    <div className="bg-card border border-border rounded-2xl shadow-xl">
      <div className="p-5 border-b border-border/60">
        <h3 className="text-lg font-bold text-foreground">Market Sentiment</h3>
        <p className="text-xs text-text-secondary">Bull vs Bear Analysis</p>
      </div>
      <div className="p-5">
        <div className="space-y-6">
          {/* Radial Gauge */}
          <div className="h-[250px] w-full">
            <ResponsiveContainer width="100%" height="100%">
              <RadialBarChart
                data={data}
                innerRadius="30%"
                outerRadius="90%"
                margin={{ top: 10, right: 10, bottom: 10, left: 10 }}
              >
                <PolarAngleAxis
                  type="number"
                  domain={[0, 100]}
                  angleAxisId={0}
                  tick={false}
                />
                <RadialBar
                  background
                  dataKey="value"
                  cornerRadius={10}
                  label={{ position: 'insideStart', fill: '#fff', fontSize: 12 }}
                />
                <Legend
                  layout="vertical"
                  verticalAlign="middle"
                  align="right"
                />
              </RadialBarChart>
            </ResponsiveContainer>
          </div>

          {/* Sentiment Overview */}
          <div className="bg-background/80 p-4 rounded-xl border border-border">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-xs font-medium text-text-secondary">Overall Sentiment</p>
                <p className={`text-xl font-bold ${sentimentColor}`}>
                  {sentimentLabel}
                </p>
              </div>
              <div className="text-right">
                <p className="text-2xl font-black text-ai-blue">
                  {sentimentScore > 0 ? '+' : ''}{sentimentScore}
                </p>
                <p className="text-[10px] text-text-secondary">Sentiment Score</p>
              </div>
            </div>
          </div>

          {/* Score Breakdown */}
          <div className="grid grid-cols-2 gap-4">
            <div className="bg-bull-green/5 p-3 rounded-xl border border-bull-green/20">
              <p className="text-xs text-bull-green font-semibold">Bull Score</p>
              <p className="text-xl font-black text-bull-green">{bullScore.toFixed(0)}</p>
              <div className="w-full bg-background rounded-full h-1.5 mt-2 overflow-hidden border border-border">
                <div
                  className="bg-bull-green h-1.5 rounded-full transition-all"
                  style={{ width: `${bullPercentage}%` }}
                />
              </div>
            </div>

            <div className="bg-bear-red/5 p-3 rounded-xl border border-bear-red/20">
              <p className="text-xs text-bear-red font-semibold">Bear Score</p>
              <p className="text-xl font-black text-bear-red">{bearScore.toFixed(0)}</p>
              <div className="w-full bg-background rounded-full h-1.5 mt-2 overflow-hidden border border-border">
                <div
                  className="bg-bear-red h-1.5 rounded-full transition-all"
                  style={{ width: `${bearPercentage}%` }}
                />
              </div>
            </div>
          </div>

          {/* Sentiment Interpretation */}
          <div className="bg-background/50 p-3 rounded-xl border border-border text-xs leading-relaxed text-text-secondary">
            {isBullish && (
              <p>
                <strong className="text-bull-green font-semibold">Bullish Signal:</strong> The majority of analysis indicators are pointing
                toward positive momentum. However, remember to conduct thorough due diligence before
                making investment decisions.
              </p>
            )}
            {isBearish && (
              <p>
                <strong className="text-bear-red font-semibold">Bearish Signal:</strong> The majority of analysis indicators are highlighting
                potential headwinds. Consider the risks carefully and do your own research.
              </p>
            )}
            {isNeutral && (
              <p>
                <strong className="text-gold-accent font-semibold">Neutral Sentiment:</strong> The analysis indicators are mixed. This suggests
                a wait-and-see approach might be prudent. Consider multiple perspectives.
              </p>
            )}
          </div>

          {/* Disclaimer */}
          <div className="bg-gold-accent/5 border border-gold-accent/20 p-3 rounded-xl text-[10px] text-text-secondary leading-normal">
            ⚠️ <strong>Disclaimer:</strong> This sentiment analysis is AI-generated educational
            research only and does NOT constitute investment advice. Always conduct your own due
            diligence and consult with financial professionals.
          </div>
        </div>
      </div>
    </div>
  );
}
