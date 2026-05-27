import { useEffect, useMemo, useRef, useState } from "react";
import ResultCard from "./ResultCard";

const API_URL = "http://localhost:8000/search";
const DEBOUNCE_MS = 300;

function RateLimitBar({ rateLimit }) {
  const limit = rateLimit?.limit ?? 30;
  const remaining = rateLimit?.remaining ?? limit;
  const percent = limit > 0 ? Math.max(0, Math.min(100, (remaining / limit) * 100)) : 0;
  const level = remaining > 20 ? "good" : remaining > 10 ? "warn" : "danger";

  return (
    <div className="rate-limit" aria-label={`${remaining} of ${limit} requests remaining`}>
      <div className="rate-limit-copy">
        <span>{remaining} / {limit} requests remaining</span>
        {rateLimit?.retry_after_remaining !== undefined && (
          <span>Resets in {rateLimit.retry_after_remaining}s</span>
        )}
      </div>
      <div className="rate-limit-track">
        <span
          className={`rate-limit-fill rate-limit-fill-${level}`}
          style={{ width: `${percent}%` }}
        />
      </div>
    </div>
  );
}

export default function SearchBox({ value, onQueryChange, onResults }) {
  const [results, setResults] = useState([]);
  const [rateLimit, setRateLimit] = useState(null);
  const [isOpen, setIsOpen] = useState(false);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState("");
  const [highlightedIndex, setHighlightedIndex] = useState(-1);
  const containerRef = useRef(null);
  const inputRef = useRef(null);

  const hasQuery = value.trim().length > 0;
  const hasResults = results.length > 0;

  const selectedResult = useMemo(() => {
    if (highlightedIndex < 0 || highlightedIndex >= results.length) {
      return null;
    }
    return results[highlightedIndex];
  }, [highlightedIndex, results]);

  useEffect(() => {
    inputRef.current?.focus();
  }, []);

  useEffect(() => {
    function handlePointerDown(event) {
      if (!containerRef.current?.contains(event.target)) {
        setIsOpen(false);
        setHighlightedIndex(-1);
      }
    }

    document.addEventListener("pointerdown", handlePointerDown);
    return () => document.removeEventListener("pointerdown", handlePointerDown);
  }, []);

  useEffect(() => {
    const query = value.trim();
    const controller = new AbortController();

    if (!query) {
      setResults([]);
      setRateLimit(null);
      setError("");
      setIsOpen(false);
      setIsLoading(false);
      setHighlightedIndex(-1);
      onResults?.({ total: 0, search_types: [] });
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

        setResults(payload.results ?? []);
        setRateLimit(payload.rate_limit ?? null);
        setIsOpen(true);
        setHighlightedIndex(payload.results?.length ? 0 : -1);
        onResults?.(payload);
      } catch (requestError) {
        if (requestError.name === "AbortError") {
          return;
        }

        setResults([]);
        setRateLimit(null);
        setIsOpen(true);
        setHighlightedIndex(-1);
        setError(requestError.message || "Search unavailable");
        onResults?.({ total: 0, search_types: [] });
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
  }, [value, onResults]);

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

    onQueryChange(result.iata);
    setIsOpen(false);
    setHighlightedIndex(-1);
  }

  function handleKeyDown(event) {
    if (event.key === "Escape") {
      setIsOpen(false);
      setHighlightedIndex(-1);
      return;
    }

    if (!isOpen && ["ArrowDown", "ArrowUp"].includes(event.key)) {
      setIsOpen(true);
    }

    if (event.key === "ArrowDown") {
      event.preventDefault();
      setHighlightedIndex((current) => Math.min(current + 1, results.length - 1));
    }

    if (event.key === "ArrowUp") {
      event.preventDefault();
      setHighlightedIndex((current) => Math.max(current - 1, 0));
    }

    if (event.key === "Enter") {
      event.preventDefault();
      selectResult(selectedResult);
    }
  }

  return (
    <div className="search-stack" ref={containerRef}>
      <div className={`search-box ${isOpen ? "search-box-active" : ""}`}>
        <span className="search-icon" aria-hidden="true" />
        <input
          ref={inputRef}
          value={value}
          onChange={(event) => onQueryChange(event.target.value)}
          onFocus={() => hasQuery && setIsOpen(true)}
          onKeyDown={handleKeyDown}
          className="search-input"
          type="search"
          placeholder="Search by city, airport, IATA, region, or alias"
          aria-label="Search airports"
          aria-expanded={isOpen}
          aria-controls="airport-results"
        />

        <div className="search-actions">
          {isLoading && <span className="spinner" aria-label="Loading search results" />}
          {hasQuery && (
            <button className="clear-button" type="button" onClick={clearSearch} aria-label="Clear search">
              ×
            </button>
          )}
        </div>
      </div>

      {isOpen && (
        <div className="results-dropdown" id="airport-results" role="listbox">
          {error && <div className="empty-state">{error}</div>}

          {!error && !isLoading && hasQuery && !hasResults && (
            <div className="empty-state">No airports found</div>
          )}

          {!error && hasResults && (
            <div className="results-list">
              {results.map((result, index) => (
                <ResultCard
                  key={result.iata}
                  result={result}
                  highlighted={index === highlightedIndex}
                  onMouseEnter={() => setHighlightedIndex(index)}
                  onSelect={() => selectResult(result)}
                />
              ))}
            </div>
          )}

          {rateLimit && <RateLimitBar rateLimit={rateLimit} />}
        </div>
      )}
    </div>
  );
}
