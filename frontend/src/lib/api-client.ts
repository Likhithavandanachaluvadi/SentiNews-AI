/**
 * API Client for SentiNews AI Backend
 * Handles all HTTP requests to the backend API
 */

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

export interface ApiErrorResponse {
  detail: string | string[];
}

export class ApiError extends Error {
  constructor(
    public status: number,
    public detail: string,
  ) {
    super(detail);
    this.name = "ApiError";
  }
}

/**
 * Generic fetch wrapper with error handling
 */
async function apiFetch<T>(
  endpoint: string,
  options?: RequestInit,
): Promise<T> {
  const url = `${API_BASE_URL}${endpoint}`;

  try {
    const response = await fetch(url, {
      ...options,
      headers: {
        "Content-Type": "application/json",
        ...options?.headers,
      },
    });

    if (!response.ok) {
      const errorData = (await response.json()) as ApiErrorResponse;
      throw new ApiError(
        response.status,
        typeof errorData.detail === "string"
          ? errorData.detail
          : errorData.detail?.join(", ") || "Unknown error",
      );
    }

    return (await response.json()) as T;
  } catch (error) {
    if (error instanceof ApiError) {
      throw error;
    }
    throw new ApiError(500, `Network error: ${(error as Error).message}`);
  }
}

/**
 * Market API endpoints
 */
export const marketApi = {
  /**
   * Get market indices (NIFTY 50, SENSEX, etc.)
   */
  async getIndices() {
    return apiFetch("/api/v1/market/indices");
  },

  /**
   * Get price history for a ticker
   */
  async getPriceHistory(ticker: string) {
    return apiFetch(`/api/v1/market/history/${encodeURIComponent(ticker)}`);
  },
};

/**
 * Analysis API endpoints
 */
export const analysisApi = {
  /**
   * Get AI analysis for a stock
   */
  async analyzeStock(query: string, ticker?: string) {
    return apiFetch("/api/v1/research/analyze", {
      method: "POST",
      body: JSON.stringify({ query, ticker }),
    });
  },

  /**
   * Get sentiment data for a stock symbol
   */
  async getSentiment(symbol: string) {
    return apiFetch("/api/v1/research/analyze", {
      method: "POST",
      body: JSON.stringify({ query: `sentiment analysis for ${symbol}`, ticker: symbol }),
    });
  },
};

/**
 * Research API endpoints
 */
export const researchApi = {
  /**
   * Execute research query
   */
  async executeQuery(query: string) {
    return apiFetch("/api/v1/research/analyze", {
      method: "POST",
      body: JSON.stringify({ query }),
    });
  },
};
