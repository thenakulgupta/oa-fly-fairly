import { useCallback, useState } from "react";
import SearchBox from "./components/SearchBox";
import TestPanel from "./components/TestPanel";
import ThemeToggle from "./components/ThemeToggle";
import "./index.css";

export default function App() {
  const [query, setQuery] = useState("");
  const [activeSearch, setActiveSearch] = useState("");
  const [resultMeta, setResultMeta] = useState({ total: 0, searchTypes: [] });

  const handleResults = useCallback((payload) => {
    setResultMeta({
      total: payload?.total ?? 0,
      searchTypes: payload?.search_types ?? [],
    });
  }, []);

  const handleTestSearch = useCallback((term) => {
    setQuery(term);
    setActiveSearch(term);
  }, []);

  const handleQueryChange = useCallback((nextQuery) => {
    setQuery(nextQuery);
    setActiveSearch(nextQuery);
  }, []);

  return (
    <main className="app-shell">
      <header className="topbar" aria-label="Application header">
        <a className="brand" href="/" aria-label="Fly Fairly home">
          <span className="brand-mark" aria-hidden="true">
            FF
          </span>
          <span>Fly Fairly</span>
        </a>
        <ThemeToggle />
      </header>

      <section className="hero" aria-labelledby="page-title">
        <p className="eyebrow">Airport intelligence</p>
        <h1 id="page-title">Search 8,000+ airports worldwide</h1>
        <p className="hero-copy">
          Fast airport lookup with IATA codes, city groups, regions, aliases, and typo-tolerant search.
        </p>
      </section>

      <section className="workspace" aria-label="Airport search workspace">
        <div className="search-column">
          <SearchBox
            value={query}
            onQueryChange={handleQueryChange}
            onResults={handleResults}
          />

          <div className="result-summary" aria-live="polite">
            <span>{resultMeta.total} results</span>
            {resultMeta.searchTypes.length > 0 && (
              <span>{resultMeta.searchTypes.join(" + ")}</span>
            )}
          </div>
        </div>

        <TestPanel activeSearch={activeSearch} onSelect={handleTestSearch} />
      </section>
    </main>
  );
}
