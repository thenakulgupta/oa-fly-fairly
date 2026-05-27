import { useEffect, useMemo, useRef, useState } from "react";
import API_BASE_URL from "../api";
import ResultCard from "./ResultCard";

const API_URL = `${API_BASE_URL}/search`;
const DEBOUNCE_MS = 300;

function RateLimitBar({ rateLimit }) {
  const limit = rateLimit?.limit ?? 30;
  const remaining = rateLimit?.remaining ?? limit;
  const percent = limit > 0 ? Math.max(0, Math.min(100, (remaining / limit) * 100)) : 0;
  const tone = remaining < 10 ? "danger" : remaining <= 20 ? "warn" : "good";

  return (
    <div className="search-rate-limit">
      <div className="rate-copy">
        <span>{remaining} / {limit} searches remaining this minute</span>
        <span>{rateLimit?.retry_after_remaining ?? 60}s reset</span>
      </div>
      <div className="rate-track" aria-hidden="true">
        <span className={`rate-fill rate-fill-${tone}`} style={{ width: `${percent}%` }} />
      </div>
    </div>
  );
}

export default function SearchBox({ value, onQueryChange, onResultSelect, onResponse }) {
  const [results, setResults] = useState([]);
  const [rateLimit, setRateLimit] = useState(null);
  const [isOpen, setIsOpen] = useState(false);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState("");
  const [highlightedIndex, setHighlightedIndex] = useState(-1);
  const inputRef = useRef(null);
  const shellRef = useRef(null);

  const trimmedQuery = value.trim();
  const hasQuery = trimmedQuery.length > 0;
  const selectedResult = useMemo(() => results[highlightedIndex], [highlightedIndex, results]);

  useEffect(() => {
    inputRef.current?.focus();
  }, []);

  useEffect(() => {
    function closeOnOutsideClick(event) {
      if (!shellRef.current?.contains(event.target)) {
        setIsOpen(false);
        setHighlightedIndex(-1);
      }
    }

    document.addEventListener("pointerdown", closeOnOutsideClick);
    return () => document.removeEventListener("pointerdown", closeOnOutsideClick);
  }, []);

  useEffect(() => {
    const query = trimmedQuery;
    const controller = new AbortController();

    if (!query) {
      setResults([]);
      setRateLimit(null);
      setIsOpen(false);
      setIsLoading(false);
      setError("");
      setHighlightedIndex(-1);
      onResponse?.({ total: 0, search_types: [], rate_limit: null });
      return undefined;
    }

    setIsLoading(true);
    setError("");

    const timeoutId = window.setTimeout(async () => {
      try {
        const url = `${API_URL}?q=${encodeURIComponent(query)}&limit=10`;
        const response = await fetch(url, { signal: controller.signal });
        const payload = await response.json();

        if (!response.ok) {
          throw new Error(payload?.error || payload?.detail || "Search failed");
        }

        const nextResults = payload.results ?? [];
        setResults(nextResults);
        setRateLimit(payload.rate_limit ?? null);
        setIsOpen(true);
        setHighlightedIndex(nextResults.length ? 0 : -1);
        onResponse?.(payload);
      } catch (requestError) {
        if (requestError.name === "AbortError") {
          return;
        }

        setResults([]);
        setRateLimit(null);
        setIsOpen(true);
        setHighlightedIndex(-1);
        setError(requestError.message || "Search unavailable");
        onResponse?.({ total: 0, search_types: [], rate_limit: null });
      } finally {
        if (!controller.signal.aborted) {
          setIsLoading(false);
        }
      }
    }, DEBOUNCE_MS);

    return () => {
      controller.abort();
      window.clearTimeout(timeoutId);
    };
  }, [trimmedQuery, onResponse]);

  function clearSearch() {
    onQueryChange("");
    setResults([]);
    setRateLimit(null);
    setIsOpen(false);
    setError("");
    setHighlightedIndex(-1);
    inputRef.current?.focus();
  }

  function selectResult(result) {
    if (!result) {
      return;
    }

    onResultSelect?.(result);
    setIsOpen(false);
    setHighlightedIndex(-1);
  }

  function handleKeyDown(event) {
    if (event.key === "Escape") {
      setIsOpen(false);
      setHighlightedIndex(-1);
      return;
    }

    if (event.key === "ArrowDown") {
      event.preventDefault();
      setIsOpen(true);
      setHighlightedIndex((current) => Math.min(current + 1, results.length - 1));
      return;
    }

    if (event.key === "ArrowUp") {
      event.preventDefault();
      setIsOpen(true);
      setHighlightedIndex((current) => Math.max(current - 1, 0));
      return;
    }

    if (event.key === "Enter") {
      event.preventDefault();
      selectResult(selectedResult);
    }
  }

  return (
    <div className="search-shell" ref={shellRef}>
      <div className={`search-frame ${isOpen ? "search-frame-open" : ""}`}>
        <span className="magnifier" aria-hidden="true">⌕</span>
        <input
          ref={inputRef}
          className="search-input"
          value={value}
          onChange={(event) => onQueryChange(event.target.value)}
          onFocus={() => hasQuery && setIsOpen(true)}
          onKeyDown={handleKeyDown}
          placeholder="City, IATA code, region, or try a typo..."
          type="search"
          aria-label="Search airports"
          aria-expanded={isOpen}
          aria-controls="search-results"
        />
        <div className="search-control">
          {isLoading ? (
            <span className="loader" aria-label="Loading" />
          ) : hasQuery ? (
            <button className="clear-search" type="button" onClick={clearSearch} aria-label="Clear search">
              ×
            </button>
          ) : null}
        </div>
      </div>

      <RateLimitBar rateLimit={rateLimit} />

      {isOpen && (
        <div className="results-popover" id="search-results" role="listbox">
          {error && <div className="empty-results">{error}</div>}
          {!error && !isLoading && hasQuery && results.length === 0 && (
            <div className="empty-results">No matching airports yet</div>
          )}

          {!error && results.length > 0 && (
            <div className="results-stack">
              {results.map((result, index) => (
                <ResultCard
                  key={`${result.iata}-${index}`}
                  result={result}
                  highlighted={highlightedIndex === index}
                  onMouseEnter={() => setHighlightedIndex(index)}
                  onOpenDetail={() => selectResult(result)}
                />
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  );
}
