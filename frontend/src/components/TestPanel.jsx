const TEST_CASES = [
  "Hawaii",
  "Bali",
  "Londn",
  "LON",
  "London",
  "東京",
  "Sao Paulo",
  "TUL",
  "Florida",
  "Manama",
  "DEL",
  "BOM",
  "JFK",
  "Brussels",
  "서울",
  "دبي",
];

export default function TestPanel({ activeSearch, onSelect }) {
  const normalizedActive = activeSearch.trim().toLocaleLowerCase();

  return (
    <aside className="test-panel" aria-labelledby="test-panel-title">
      <div className="test-panel-header">
        <h2 id="test-panel-title">Test Cases</h2>
        <p>Click to search</p>
      </div>

      <div className="test-chips" role="list">
        {TEST_CASES.map((term) => {
          const active = normalizedActive === term.toLocaleLowerCase();

          return (
            <button
              key={term}
              className={`test-chip ${active ? "test-chip-active" : ""}`}
              type="button"
              onClick={() => onSelect(term)}
              aria-pressed={active}
            >
              {term}
            </button>
          );
        })}
      </div>
    </aside>
  );
}
