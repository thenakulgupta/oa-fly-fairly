const TEST_CASES = [
  { icon: "🏝", query: "Hawaii", description: "State/region search" },
  { icon: "🌴", query: "Bali", description: "Tourism alias" },
  { icon: "✈", query: "LON", description: "Multi-airport city code" },
  { icon: "🇬🇧", query: "London", description: "Disambiguation" },
  { icon: "⌨", query: "Londn", description: "Typo tolerance" },
  { icon: "🗼", query: "東京", description: "Japanese script" },
  { icon: "🇰🇷", query: "서울", description: "Korean script" },
  { icon: "🇧🇭", query: "Manama", description: "City to airport" },
  { icon: "🌎", query: "Sao Paulo", description: "Accent insensitive" },
  { icon: "✈", query: "TUL", description: "IATA reverse lookup" },
  { icon: "🌴", query: "Florida", description: "State vs Chile noise" },
  { icon: "🇧🇪", query: "Brussels", description: "Alias vs municipality" },
];

export default function TestPanel({ activeSearch, onSelect }) {
  const active = activeSearch.trim().toLocaleLowerCase();

  return (
    <section className="test-playground" aria-labelledby="test-title">
      <div className="section-heading">
        <p>EDGE CASE PLAYGROUND</p>
        <h2 id="test-title">These are real failure cases from production</h2>
      </div>

      <div className="test-grid">
        {TEST_CASES.map((item) => {
          const isActive = active === item.query.toLocaleLowerCase();

          return (
            <button
              key={item.query}
              className={`test-card ${isActive ? "test-card-active" : ""}`}
              type="button"
              onClick={() => onSelect(item.query)}
            >
              <span className="test-icon" aria-hidden="true">{item.icon}</span>
              <strong>{item.query}</strong>
              <span>{item.description}</span>
            </button>
          );
        })}
      </div>
    </section>
  );
}
