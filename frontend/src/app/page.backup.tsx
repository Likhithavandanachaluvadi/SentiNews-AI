"use client";

import { useState, useEffect } from "react";
import {
  Search,
  ChevronRight,
  Sparkles,
  AlertTriangle,
  TrendingUp,
  TrendingDown,
  Clock,
  BookOpen,
  BarChart3,
  MessageSquare,
  Award,
  FileText,
  CheckCircle,
  ExternalLink,
  Calendar,
  ArrowLeft,
  Activity,
  Cpu,
  Layers,
} from "lucide-react";
import { motion, AnimatePresence } from "framer-motion";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";

import StockChart from "@/components/StockChart";
import SentimentMeter from "@/components/SentimentMeter";

interface Citation {
  title: string;
  source: string;
  url: string;
  published_at: string;
}

interface AnalysisResponse {
  report_id: string;
  ticker: string;
  company_name?: string;
  executive_summary: string;
  fundamental_analysis: string;
  technical_analysis: string;
  sentiment_analysis: string;
  conclusion: string;
  risk_disclaimer: string;
  citations: Citation[];
  sentiment_score: number;
  generation_time_ms: number;
  created_at: string;
}

interface IndexData {
  name: string;
  ticker: string;
  price: number;
  change: number;
  change_percent: number;
  sparkline: number[];
}

const MOCK_INDICES: IndexData[] = [
  {
    name: "NIFTY 50",
    ticker: "^NSEI",
    price: 22055.2,
    change: 125.4,
    change_percent: 0.57,
    sparkline: [21900, 21950, 21920, 21990, 22010, 22030, 22055.2],
  },
  {
    name: "SENSEX",
    ticker: "^BSESN",
    price: 72612.3,
    change: 410.15,
    change_percent: 0.57,
    sparkline: [72100, 72300, 72150, 72400, 72480, 72550, 72612.3],
  },
  {
    name: "NIFTY BANK",
    ticker: "^NSEBANK",
    price: 47482.4,
    change: -180.2,
    change_percent: -0.38,
    sparkline: [47800, 47700, 47900, 47600, 47550, 47620, 47482.4],
  },
  {
    name: "NIFTY IT",
    ticker: "^CNXIT",
    price: 34105.1,
    change: 340.5,
    change_percent: 1.01,
    sparkline: [33600, 33750, 33700, 33900, 33950, 34020, 34105.1],
  },
];

const TRENDING_TICKERS = [
  { symbol: "RELIANCE", name: "Reliance Industries" },
  { symbol: "TCS", name: "Tata Consultancy Services" },
  { symbol: "HDFCBANK", name: "HDFC Bank" },
  { symbol: "INFY", name: "Infosys" },
  { symbol: "ICICIBANK", name: "ICICI Bank" },
  { symbol: "M&M", name: "Mahindra & Mahindra" },
];

// Mock trending reports data for today
const TRENDING_REPORTS_TODAY = [
  {
    ticker: "RELIANCE",
    name: "Reliance Industries",
    reportsCount: 342,
    sentiment: 7.2,
    sentimentChange: 0.8,
    price: 3092.3,
    priceChange: 1.2,
    category: "Energy & Petrochemicals",
  },
  {
    ticker: "TCS",
    name: "Tata Consultancy Services",
    reportsCount: 287,
    sentiment: 6.8,
    sentimentChange: 0.5,
    price: 4156.75,
    priceChange: 2.1,
    category: "IT Services",
  },
  {
    ticker: "INFY",
    name: "Infosys Limited",
    reportsCount: 265,
    sentiment: 6.5,
    sentimentChange: -0.3,
    price: 1876.5,
    priceChange: -0.8,
    category: "IT Services",
  },
  {
    ticker: "HDFCBANK",
    name: "HDFC Bank",
    reportsCount: 198,
    sentiment: 7.1,
    sentimentChange: 1.2,
    price: 1642.8,
    priceChange: 0.6,
    category: "Banking",
  },
  {
    ticker: "ICICIBANK",
    name: "ICICI Bank",
    reportsCount: 176,
    sentiment: 6.9,
    sentimentChange: 0.4,
    price: 1098.45,
    priceChange: 1.8,
    category: "Banking",
  },
  {
    ticker: "M&M",
    name: "Mahindra & Mahindra",
    reportsCount: 143,
    sentiment: 6.3,
    sentimentChange: -0.6,
    price: 2845.2,
    priceChange: -1.2,
    category: "Automotive",
  },
];

export default function Home() {
  const [query, setQuery] = useState("");
  const [isSearching, setIsSearching] = useState(false);
  const [report, setReport] = useState<AnalysisResponse | null>(null);
  const [activeTab, setActiveTab] = useState<string>("summary");
  const [indices, setIndices] = useState<IndexData[]>([]);
  const [isLoadingIndices, setIsLoadingIndices] = useState(true);

  const formatMarkdown = (text: string) => {
    if (!text) return "";
    return text.replace(/\\n/g, "\n");
  };

  // Fetch indices on mount
  useEffect(() => {
    const fetchIndices = async () => {
      try {
        const res = await fetch("http://localhost:/api/v1/market/indices");
        if (res.ok) {
          const data = await res.json();
          if (data && data.length > 0) {
            setIndices(data);
            return;
          }
        }
        setIndices(MOCK_INDICES);
      } catch (error) {
        console.error("Failed to fetch market indices:", error);
        setIndices(MOCK_INDICES);
      } finally {
        setIsLoadingIndices(false);
      }
    };

    fetchIndices();
    const interval = setInterval(fetchIndices, 45000); // refresh every 45s
    return () => clearInterval(interval);
  }, []);

  const handleSearch = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!query.trim()) return;
    await executeQuery(query);
  };

  const handleTrendingClick = async (symbol: string) => {
    setQuery(symbol);
    await executeQuery(symbol);
  };

  const executeQuery = async (searchQuery: string) => {
    setIsSearching(true);
    try {
      const res = await fetch("http://localhost:/api/v1/research/analyze", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ query: searchQuery }),
      });

      if (!res.ok) {
        let errMsg = "Failed to fetch report";
        try {
          const errJson = await res.json();
          if (errJson && errJson.detail) {
            errMsg = errJson.detail;
          }
        } catch (_) { }
        throw new Error(errMsg);
      }

      const data: AnalysisResponse = await res.json();
      setReport(data);
      setActiveTab("summary");
    } catch (error) {
      console.error(error);
      const isConnectionError =
        error instanceof Error && error.message.includes("fetch");
      setReport({
        report_id: "error",
        ticker: searchQuery.split(" ").pop()?.toUpperCase() || "ERROR",
        company_name: isConnectionError
          ? "Service Unreachable"
          : "Request Rejected",
        executive_summary: isConnectionError
          ? "### Connection Issue\n\nCould not fetch analysis report from the backend server. Please verify that the FastAPI backend is running on `http://localhost:`."
          : `### Validation Error\n\n${error instanceof Error ? error.message : "Failed to analyze query."}`,
        fundamental_analysis: "",
        technical_analysis: "",
        sentiment_analysis: "",
        conclusion: "",
        risk_disclaimer: isConnectionError
          ? "No backend connection. Run the backend service and verify API keys to generate reports."
          : "Please adjust your query and try again.",
        citations: [],
        sentiment_score: 0,
        generation_time_ms: 0,
        created_at: new Date().toISOString(),
      });
    } finally {
      setIsSearching(false);
    }
  };

  const handleBack = () => {
    setReport(null);
    setQuery("");
  };

  const getSentimentLabel = (score: number) => {
    if (score >= 40)
      return {
        text: "Strongly Bullish",
        color: "text-bull-green bg-bull-green/10 border-bull-green/20",
      };
    if (score >= 10)
      return {
        text: "Moderately Bullish",
        color: "text-emerald-400 bg-emerald-400/10 border-emerald-400/20",
      };
    if (score <= -40)
      return {
        text: "Strongly Bearish",
        color: "text-bear-red bg-bear-red/10 border-bear-red/20",
      };
    if (score <= -10)
      return {
        text: "Moderately Bearish",
        color: "text-rose-400 bg-rose-400/10 border-rose-400/20",
      };
    return {
      text: "Neutral / Mixed",
      color: "text-gold-accent bg-gold-accent/10 border-gold-accent/20",
    };
  };

  const sentiment = report ? getSentimentLabel(report.sentiment_score) : null;

  // Custom SVG Sparkline generator
  const renderSparkline = (dataPoints: number[], isPositive: boolean) => {
    if (!dataPoints || dataPoints.length === 0) return null;
    const min = Math.min(...dataPoints);
    const max = Math.max(...dataPoints);
    const range = max - min || 1;
    const width = 70;
    const height = 24;
    const points = dataPoints
      .map((val, index) => {
        const x = (index / (dataPoints.length - 1)) * width;
        const y = height - ((val - min) / range) * height;
        return `${x},${y}`;
      })
      .join(" ");

    const strokeColor = isPositive ? "var(--bull-green)" : "var(--bear-red)";
    return (
      <svg width={width} height={height} className="overflow-visible">
        <polyline
          fill="none"
          stroke={strokeColor}
          strokeWidth="1.5"
          points={points}
        />
      </svg>
    );
  };

  return (
    <div className="flex flex-col items-center max-w-7xl mx-auto w-full px-2 md:px-4">
      <AnimatePresence mode="wait">
        {!report ? (
          // Landing Dashboard View
          <motion.div
            key="landing"
            initial={{ opacity: 0, y: 15 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -15 }}
            transition={{ duration: 0.3 }}
            className="w-full space-y-10"
          >
            {/* Live Major Indices */}
            <div className="grid grid-cols-2 lg:grid-cols-4 gap-4 pt-4">
              {(indices.length > 0 ? indices : MOCK_INDICES).map((idx) => {
                const isPositive = idx.change >= 0;
                return (
                  <div
                    key={idx.name}
                    className="glass-panel rounded-2xl p-4 flex items-center justify-between shadow-lg relative overflow-hidden"
                  >
                    <div className="space-y-1">
                      <p className="text-xs font-bold text-text-secondary tracking-wider">
                        {idx.name}
                      </p>
                      <p className="text-lg font-black text-white font-mono">
                        {idx.price.toLocaleString("en-IN", {
                          minimumFractionDigits: 2,
                        })}
                      </p>
                      <div className="flex items-center gap-1.5 text-xs">
                        <span
                          className={`font-semibold flex items-center ${isPositive ? "text-bull-green" : "text-bear-red"}`}
                        >
                          {isPositive ? "+" : ""}
                          {idx.change_percent.toFixed(2)}%
                        </span>
                        <span className="text-[10px] text-text-secondary">
                          7D
                        </span>
                      </div>
                    </div>
                    <div className="pl-4">
                      {renderSparkline(idx.sparkline, isPositive)}
                    </div>
                  </div>
                );
              })}
            </div>

            {/* Hero Brand Title */}
            <div className="text-center space-y-4 py-8">
              <div className="inline-flex items-center gap-2 px-3 py-1.5 rounded-full bg-ai-blue/10 border border-ai-blue/30 text-xs font-semibold text-text-secondary select-none">
                <Sparkles className="h-3.5 w-3.5 text-ai-blue" />
                Next-Gen Multi-Agent Market Intelligence
              </div>
              <h1 className="text-4xl md:text-6xl font-extrabold tracking-tight text-white leading-tight">
                with
                <br />
                <span className="text-transparent bg-clip-text bg-gradient-to-r from-ai-blue via-cyan-400 to-bull-green bg-[length:200%_auto] animate-pulse">
                  Sentinews Financial Intelligence
                </span>
              </h1>
              <p className="text-text-secondary text-sm md:text-base max-w-xl mx-auto">
                Generate real-time, institutional-grade stock analysis sheets.
                SentiNews cross-references fundamentals, technical indicators,
                and media sentiment.
              </p>
            </div>

            {/* Central Terminal Command Center */}
            <div className="w-full max-w-3xl mx-auto space-y-4">
              <form onSubmit={handleSearch} className="relative group">
                <div className="absolute inset-y-0 left-5 flex items-center pointer-events-none">
                  <Search className="h-5 w-5 text-text-secondary group-focus-within:text-ai-blue transition-colors" />
                </div>
                <input
                  suppressHydrationWarning
                  type="text"
                  value={query}
                  onChange={(e) => setQuery(e.target.value)}
                  placeholder="Analyze TCS, Reliance growth forecast, or enter ticker..."
                  className="w-full bg-card/65 border border-border text-foreground rounded-2xl py-5 pl-14 pr-36 focus:outline-none focus:ring-2 focus:ring-ai-blue/50 focus:border-ai-blue/70 transition-all shadow-2xl text-base placeholder-text-secondary/60 backdrop-blur-md"
                />
                <div className="absolute inset-y-2 right-2 flex items-center">
                  <button
                    suppressHydrationWarning
                    type="submit"
                    disabled={isSearching || !query.trim()}
                    className="bg-ai-blue hover:bg-blue-600 disabled:bg-border/60 disabled:text-text-secondary/50 text-white rounded-xl px-5 py-3 flex items-center gap-2 font-semibold transition-all shadow-lg hover:shadow-ai-blue/20 cursor-pointer"
                  >
                    {isSearching ? (
                      <span className="flex items-center gap-2">
                        <span className="animate-spin h-4 w-4 border-2 border-white border-t-transparent rounded-full"></span>
                        Analyzing
                      </span>
                    ) : (
                      <span className="flex items-center gap-1">
                        Research <ChevronRight className="h-4.5 w-4.5" />
                      </span>
                    )}
                  </button>
                </div>
              </form>

              {/* Trending Tickers Chips */}
              <div className="flex flex-wrap items-center justify-center gap-2 text-xs text-text-secondary">
                <span className="font-semibold mr-1 flex items-center gap-1">
                  <Activity className="h-3.5 w-3.5 text-ai-blue" />
                  Popular:
                </span>
                {TRENDING_TICKERS.map((stock) => (
                  <button
                    suppressHydrationWarning
                    key={stock.symbol}
                    onClick={() => handleTrendingClick(stock.symbol)}
                    className="bg-[#121D3A] hover:bg-ai-blue/15 border border-[#1E2C4F] hover:border-ai-blue/50 text-foreground px-3 py-1.5 rounded-lg transition-all cursor-pointer font-medium"
                  >
                    {stock.symbol}
                  </button>
                ))}
              </div>
            </div>

            {/* Today's Trending Reports Section */}
            <div className="pt-12 space-y-6">
              <div className="text-center space-y-2">
                <div className="flex items-center justify-center gap-2">
                  <TrendingUp className="h-5 w-5 text-bull-green" />
                  <h2 className="text-2xl md:text-3xl font-black text-white">
                    Today's Most Analyzed Stocks
                  </h2>
                </div>
                <p className="text-text-secondary text-sm">
                  Real-time trending reports generated by institutional
                  investors
                </p>
              </div>

              {/* Trending Reports Grid */}
              <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
                {TRENDING_REPORTS_TODAY.map((report, idx) => (
                  <motion.div
                    key={report.ticker}
                    initial={{ opacity: 0, y: 10 }}
                    whileInView={{ opacity: 1, y: 0 }}
                    transition={{ delay: idx * 0.05, duration: 0.3 }}
                    onClick={() => handleTrendingClick(report.ticker)}
                    className="glass-panel glass-panel-hover rounded-xl p-4 cursor-pointer group"
                  >
                    {/* Header: Ticker + Badge */}
                    <div className="flex items-start justify-between mb-3">
                      <div>
                        <h3 className="text-lg font-bold text-white group-hover:text-ai-blue transition-colors">
                          {report.ticker}
                        </h3>
                        <p className="text-xs text-text-secondary">
                          {report.name}
                        </p>
                      </div>
                      <span className="bg-ai-blue/20 border border-ai-blue/40 text-ai-blue text-[10px] font-bold px-2 py-1 rounded">
                        #{idx + 1} TRENDING
                      </span>
                    </div>

                    {/* Category */}
                    <p className="text-xs text-text-secondary/70 mb-3 pb-3 border-b border-border/50">
                      {report.category}
                    </p>

                    {/* Metrics Grid */}
                    <div className="space-y-2.5 mb-3">
                      {/* Reports Count */}
                      <div className="flex items-center justify-between">
                        <span className="text-xs text-text-secondary flex items-center gap-1">
                          <Activity className="h-3.5 w-3.5 text-ai-blue" />
                          Reports
                        </span>
                        <span className="text-sm font-bold text-white">
                          {report.reportsCount}
                        </span>
                      </div>

                      {/* Sentiment Score */}
                      <div className="flex items-center justify-between">
                        <span className="text-xs text-text-secondary flex items-center gap-1">
                          <MessageSquare className="h-3.5 w-3.5 text-gold-accent" />
                          Sentiment
                        </span>
                        <span className="text-sm font-bold">
                          <span className="text-white">
                            {report.sentiment.toFixed(1)}
                          </span>
                          <span
                            className={`ml-1 text-xs font-semibold ${report.sentimentChange >= 0 ? "text-bull-green" : "text-bear-red"}`}
                          >
                            {report.sentimentChange >= 0 ? "+" : ""}
                            {report.sentimentChange.toFixed(1)}
                          </span>
                        </span>
                      </div>

                      {/* Price */}
                      <div className="flex items-center justify-between">
                        <span className="text-xs text-text-secondary">
                          Price
                        </span>
                        <div className="text-right">
                          <p className="text-sm font-bold text-white">
                            ₹{report.price.toFixed(2)}
                          </p>
                          <p
                            className={`text-xs font-semibold ${report.priceChange >= 0 ? "text-bull-green" : "text-bear-red"}`}
                          >
                            {report.priceChange >= 0 ? "▲" : "▼"}{" "}
                            {Math.abs(report.priceChange).toFixed(1)}%
                          </p>
                        </div>
                      </div>
                    </div>

                    {/* CTA Button */}
                    <button className="w-full mt-3 pt-3 border-t border-border/50 text-xs font-semibold text-ai-blue hover:text-blue-300 transition-colors flex items-center justify-between group/btn">
                      View Full Analysis
                      <ChevronRight className="h-3.5 w-3.5 group-hover/btn:translate-x-0.5 transition-transform" />
                    </button>
                  </motion.div>
                ))}
              </div>
            </div>

            {/* Divider */}
            <div className="h-px bg-gradient-to-r from-transparent via-border to-transparent my-8" />

            {/* Platform Capabilities Grid */}
            <div className="grid grid-cols-1 md:grid-cols-3 gap-6 pt-8">
              <div className="glass-panel glass-panel-hover rounded-2xl p-6 space-y-4">
                <div className="h-10 w-10 rounded-xl bg-ai-blue/10 border border-ai-blue/30 flex items-center justify-center">
                  <Layers className="h-5 w-5 text-ai-blue" />
                </div>
                <h3 className="text-lg font-bold text-white">
                  Parallel Research Agents
                </h3>
                <p className="text-xs text-text-secondary leading-relaxed">
                  SentiNews orchestrates specialized sub-agents. They analyze
                  financial statements, inspect price actions, and filter news
                  streams in parallel.
                </p>
              </div>

              <div className="glass-panel glass-panel-hover rounded-2xl p-6 space-y-4">
                <div className="h-10 w-10 rounded-xl bg-bull-green/10 border border-bull-green/30 flex items-center justify-center">
                  <Cpu className="h-5 w-5 text-bull-green" />
                </div>
                <h3 className="text-lg font-bold text-white">
                  RAG Filings Synthesis
                </h3>
                <p className="text-xs text-text-secondary leading-relaxed">
                  Ingests live context from yfinance database nodes and Qdrant
                  semantic indexes to verify claims against registered company
                  filings.
                </p>
              </div>

              <div className="glass-panel glass-panel-hover rounded-2xl p-6 space-y-4">
                <div className="h-10 w-10 rounded-xl bg-gold-accent/10 border border-gold-accent/30 flex items-center justify-center">
                  <MessageSquare className="h-5 w-5 text-gold-accent" />
                </div>
                <h3 className="text-lg font-bold text-white">
                  Consensus Verification
                </h3>
                <p className="text-xs text-text-secondary leading-relaxed">
                  A final LLM Juror validates evidence, flags structural
                  discrepancies, evaluates overall risks, and exports structured
                  reports.
                </p>
              </div>
            </div>
          </motion.div>
        ) : (
          // Active Analysis View Workspace
          <motion.div
            key="workspace"
            initial={{ opacity: 0, y: 15 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -15 }}
            transition={{ duration: 0.3 }}
            className="w-full space-y-6"
          >
            {/* Top Back/Symbol Nav Bar */}
            <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 bg-card border border-border p-5 rounded-2xl shadow-xl">
              <div className="flex items-center gap-3">
                <button
                  onClick={handleBack}
                  className="bg-background hover:bg-border p-2.5 rounded-xl border border-border transition-colors cursor-pointer text-text-secondary hover:text-foreground"
                >
                  <ArrowLeft className="h-4 w-4" />
                </button>
                <div>
                  <div className="flex items-center gap-2">
                    <h2 className="text-2xl font-black text-white">
                      {report.ticker}
                    </h2>
                    {report.company_name && (
                      <span className="text-xs bg-ai-blue/15 border border-ai-blue/30 px-2 py-0.5 rounded text-ai-blue font-bold uppercase tracking-wider">
                        {report.company_name}
                      </span>
                    )}
                  </div>
                  <p className="text-xs text-text-secondary flex items-center gap-1.5 mt-0.5">
                    <Activity className="h-3 w-3 text-bull-green" /> NSE Listed
                    Equity
                  </p>
                </div>
              </div>

              {/* Research Performance Stats */}
              <div className="flex items-center gap-6 text-xs border-t md:border-t-0 border-border/50 pt-3 md:pt-0">
                <div className="space-y-0.5">
                  <p className="text-text-secondary flex items-center gap-1">
                    <Clock className="h-3.5 w-3.5" /> Latency
                  </p>
                  <p className="font-bold text-white font-mono">
                    {(report.generation_time_ms / 1000).toFixed(2)}s
                  </p>
                </div>
                <div className="space-y-0.5">
                  <p className="text-text-secondary flex items-center gap-1">
                    <Calendar className="h-3.5 w-3.5" /> Compiled
                  </p>
                  <p className="font-bold text-white font-mono">
                    {report.created_at.slice(0, 10)}
                  </p>
                </div>
                <div className="space-y-0.5">
                  <p className="text-text-secondary">Report ID</p>
                  <p className="font-mono text-[10px] text-text-secondary/70 truncate max-w-[80px]">
                    {report.report_id}
                  </p>
                </div>
              </div>
            </div>

            {/* Visual Analytics Row: Chart (Left) + Sentiment Dial (Right) */}
            {report.report_id !== "error" && (
              <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
                <div className="lg:col-span-2">
                  <StockChart ticker={report.ticker} />
                </div>
                <div className="lg:col-span-1">
                  <SentimentMeter
                    bullScore={50 + report.sentiment_score / 2}
                    bearScore={50 - report.sentiment_score / 2}
                    sentimentScore={report.sentiment_score}
                  />
                </div>
              </div>
            )}

            {/* Report Content Panel */}
            <div className="grid grid-cols-1 gap-6">
              {/* Tab Navigation Menu */}
              <div className="bg-card border border-border rounded-xl p-1.5 flex flex-wrap gap-1 shadow-md">
                {[
                  { id: "summary", label: "Executive Summary", icon: FileText },
                  { id: "fundamental", label: "Fundamentals", icon: Award },
                  {
                    id: "technical",
                    label: "Technical Setup",
                    icon: BarChart3,
                  },
                  {
                    id: "sentiment",
                    label: "Sentiment Synthesis",
                    icon: MessageSquare,
                  },
                  {
                    id: "conclusion",
                    label: "Synthesis Verdict",
                    icon: CheckCircle,
                  },
                  {
                    id: "citations",
                    label: `Citations (${report.citations.length})`,
                    icon: BookOpen,
                  },
                ].map((tab) => {
                  const Icon = tab.icon;
                  const isActive = activeTab === tab.id;
                  return (
                    <button
                      key={tab.id}
                      onClick={() => setActiveTab(tab.id)}
                      className={`flex items-center gap-2 px-4 py-2.5 rounded-lg text-xs md:text-sm font-semibold transition-all cursor-pointer ${isActive
                          ? "bg-ai-blue text-white shadow-[0_0_12px_rgba(76,111,255,0.3)]"
                          : "text-text-secondary hover:text-foreground hover:bg-background/40"
                        }`}
                    >
                      <Icon className="h-4 w-4" />
                      {tab.label}
                    </button>
                  );
                })}
              </div>

              {/* Viewport Content Panel */}
              <div className="bg-card border border-border rounded-2xl p-6 md:p-8 min-h-[350px] shadow-2xl relative overflow-hidden">
                <AnimatePresence mode="wait">
                  <motion.div
                    key={activeTab}
                    initial={{ opacity: 0, x: 8 }}
                    animate={{ opacity: 1, x: 0 }}
                    exit={{ opacity: 0, x: -8 }}
                    transition={{ duration: 0.2 }}
                    className="text-foreground leading-relaxed font-sans"
                  >
                    {/* Executive Summary */}
                    {activeTab === "summary" && (
                      <div className="space-y-4">
                        <div className="flex items-center gap-2 border-b border-border pb-3 mb-4">
                          <FileText className="h-5 w-5 text-ai-blue" />
                          <h3 className="text-lg font-bold text-white">
                            Executive Summary
                          </h3>
                        </div>
                        <div className="markdown-body">
                          <ReactMarkdown remarkPlugins={[remarkGfm]}>
                            {formatMarkdown(report.executive_summary)}
                          </ReactMarkdown>
                        </div>
                      </div>
                    )}

                    {/* Fundamental Analysis */}
                    {activeTab === "fundamental" && (
                      <div className="space-y-4">
                        <div className="flex items-center gap-2 border-b border-border pb-3 mb-4">
                          <Award className="h-5 w-5 text-emerald-400" />
                          <h3 className="text-lg font-bold text-white">
                            Fundamental Assessment
                          </h3>
                        </div>
                        {report.fundamental_analysis ? (
                          <div className="markdown-body">
                            <ReactMarkdown remarkPlugins={[remarkGfm]}>
                              {formatMarkdown(report.fundamental_analysis)}
                            </ReactMarkdown>
                          </div>
                        ) : (
                          <p className="text-text-secondary italic text-sm">
                            No fundamental assessment payload fetched for this
                            asset. Verify corporate filing connections.
                          </p>
                        )}
                      </div>
                    )}

                    {/* Technical Setup */}
                    {activeTab === "technical" && (
                      <div className="space-y-4">
                        <div className="flex items-center gap-2 border-b border-border pb-3 mb-4">
                          <BarChart3 className="h-5 w-5 text-ai-blue" />
                          <h3 className="text-lg font-bold text-white">
                            Technical Analysis & Volatility Levels
                          </h3>
                        </div>
                        {report.technical_analysis ? (
                          <div className="markdown-body">
                            <ReactMarkdown remarkPlugins={[remarkGfm]}>
                              {formatMarkdown(report.technical_analysis)}
                            </ReactMarkdown>
                          </div>
                        ) : (
                          <p className="text-text-secondary italic text-sm">
                            No technical setup charts retrieved. Index prices
                            and moving averages might be offline.
                          </p>
                        )}
                      </div>
                    )}

                    {/* Sentiment Synthesis */}
                    {activeTab === "sentiment" && (
                      <div className="space-y-4">
                        <div className="flex items-center gap-2 border-b border-border pb-3 mb-4">
                          <MessageSquare className="h-5 w-5 text-gold-accent" />
                          <h3 className="text-lg font-bold text-white">
                            Media & News Sentiment Index
                          </h3>
                        </div>
                        {report.sentiment_analysis ? (
                          <div className="markdown-body">
                            <ReactMarkdown remarkPlugins={[remarkGfm]}>
                              {formatMarkdown(report.sentiment_analysis)}
                            </ReactMarkdown>
                          </div>
                        ) : (
                          <p className="text-text-secondary italic text-sm">
                            No public NLP sentiment metrics generated for this
                            stock query.
                          </p>
                        )}
                      </div>
                    )}

                    {/* Conclusion Verdict */}
                    {activeTab === "conclusion" && (
                      <div className="space-y-4">
                        <div className="flex items-center gap-2 border-b border-border pb-3 mb-4">
                          <CheckCircle className="h-5 w-5 text-bull-green" />
                          <h3 className="text-lg font-bold text-white">
                            Synthesis Recommendation Verdict
                          </h3>
                        </div>
                        <div className="markdown-body">
                          <ReactMarkdown remarkPlugins={[remarkGfm]}>
                            {formatMarkdown(report.conclusion)}
                          </ReactMarkdown>
                        </div>
                      </div>
                    )}

                    {/* Source Citations */}
                    {activeTab === "citations" && (
                      <div className="space-y-4">
                        <div className="flex items-center gap-2 border-b border-border pb-3 mb-4">
                          <BookOpen className="h-5 w-5 text-ai-blue" />
                          <h3 className="text-lg font-bold text-white">
                            Document Sources & References
                          </h3>
                        </div>
                        {report.citations.length > 0 ? (
                          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                            {report.citations.map((cite, index) => (
                              <div
                                key={index}
                                className="bg-background/45 border border-border/80 p-5 rounded-2xl hover:border-ai-blue/35 transition-all flex flex-col justify-between"
                              >
                                <div className="space-y-2">
                                  <div className="flex justify-between items-center text-[10px] font-bold uppercase text-text-secondary">
                                    <span className="bg-border px-2 py-0.5 rounded text-white">
                                      {cite.source}
                                    </span>
                                    {cite.published_at && (
                                      <span>
                                        {new Date(
                                          cite.published_at,
                                        ).toLocaleDateString()}
                                      </span>
                                    )}
                                  </div>
                                  <h4 className="font-bold text-sm text-white line-clamp-3 leading-normal">
                                    {cite.title}
                                  </h4>
                                </div>
                                {cite.url && (
                                  <a
                                    href={cite.url}
                                    target="_blank"
                                    rel="noopener noreferrer"
                                    className="text-xs text-ai-blue hover:underline font-semibold flex items-center gap-1.5 self-start mt-4"
                                  >
                                    View Source Document{" "}
                                    <ExternalLink className="h-3 w-3" />
                                  </a>
                                )}
                              </div>
                            ))}
                          </div>
                        ) : (
                          <p className="text-text-secondary italic text-sm">
                            No external publications found. Using local baseline
                            indices context.
                          </p>
                        )}
                      </div>
                    )}
                  </motion.div>
                </AnimatePresence>
              </div>

              {/* Disclaimer */}
              <div className="bg-card/35 border border-border p-4 rounded-xl text-xs text-text-secondary flex items-start gap-3">
                <AlertTriangle className="h-4.5 w-4.5 text-gold-accent flex-shrink-0 mt-0.5" />
                <p>
                  <strong>Security & Risk Disclaimer:</strong>{" "}
                  {report.risk_disclaimer ||
                    "All educational research compiled by SentiNews AI relies on automated data scrapers and LLM evaluators. Content does not represent direct financial counsel."}
                </p>
              </div>
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}
