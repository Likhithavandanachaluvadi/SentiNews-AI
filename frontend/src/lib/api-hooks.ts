/**
 * React Query Hooks for SentiNews AI
 * Provides reusable data fetching hooks with caching and error handling
 */

import { useQuery, UseQueryResult } from "@tanstack/react-query";
import { marketApi, analysisApi, researchApi } from "./api-client";

const QUERY_STALE_TIME = 5 * 60 * 1000; // 5 minutes
const QUERY_CACHE_TIME = 10 * 60 * 1000; // 10 minutes

/**
 * Hook for fetching market indices
 */
export function useMarketIndices(): UseQueryResult<any> {
  return useQuery({
    queryKey: ["market", "indices"],
    queryFn: () => marketApi.getIndices(),
    staleTime: QUERY_STALE_TIME,
    gcTime: QUERY_CACHE_TIME,
    retry: 2,
  });
}

/**
 * Hook for fetching price history for a ticker
 */
export function usePriceHistory(ticker: string | null): UseQueryResult<any> {
  return useQuery({
    queryKey: ["market", "history", ticker],
    queryFn: () => marketApi.getPriceHistory(ticker!),
    enabled: !!ticker,
    staleTime: QUERY_STALE_TIME,
    gcTime: QUERY_CACHE_TIME,
    retry: 2,
  });
}

/**
 * Hook for getting stock analysis
 */
export function useStockAnalysis(symbol: string | null): UseQueryResult<any> {
  return useQuery({
    queryKey: ["analysis", "stock", symbol],
    queryFn: () => analysisApi.analyzeStock(symbol!),
    enabled: !!symbol,
    staleTime: 15 * 60 * 1000, // 15 minutes
    gcTime: 30 * 60 * 1000, // 30 minutes
    retry: 1,
  });
}

/**
 * Hook for getting sentiment data
 */
export function useSentiment(symbol: string | null): UseQueryResult<any> {
  return useQuery({
    queryKey: ["analysis", "sentiment", symbol],
    queryFn: () => analysisApi.getSentiment(symbol!),
    enabled: !!symbol,
    staleTime: QUERY_STALE_TIME,
    gcTime: QUERY_CACHE_TIME,
    retry: 2,
  });
}

/**
 * Hook for executing research query
 */
export function useResearchQuery(query: string | null): UseQueryResult<any> {
  return useQuery({
    queryKey: ["research", "query", query],
    queryFn: () => researchApi.executeQuery(query!),
    enabled: !!query,
    staleTime: 20 * 60 * 1000, // 20 minutes
    gcTime: 60 * 60 * 1000, // 1 hour
    retry: 1,
  });
}
