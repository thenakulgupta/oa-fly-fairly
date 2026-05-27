const MATCH_LABELS = {
  iata_exact: "Exact IATA",
  city_exact: "City",
  region_match: "Region",
  fuzzy_match: "Fuzzy",
  city_group_match: "City group",
};

function flagEmoji(countryCode) {
  if (!countryCode || countryCode.length !== 2) {
    return "";
  }

  return countryCode
    .toUpperCase()
    .replace(/./g, (letter) => String.fromCodePoint(127397 + letter.charCodeAt(0)));
}

function typeLabel(type) {
  return type?.replaceAll("_", " ") || "Airport";
}

export default function AirportDetail({ airport, onClose }) {
  if (!airport) {
    return null;
  }

  const aliases = airport.city_aliases ?? [];
  const matchTypes = airport.match_types ?? [];
  const subAirports = airport.sub_airports ?? [];
  const flag = flagEmoji(airport.country_code);

  return (
    <div className="detail-layer" role="dialog" aria-modal="true" aria-label={`${airport.iata} details`}>
      <button className="detail-backdrop" type="button" onClick={onClose} aria-label="Close detail" />

      <aside className="airport-detail">
        <header className="detail-header">
          <div>
            <span className="detail-iata">{airport.iata}</span>
            <h2>{airport.name}</h2>
            <p>
              {flag && <span>{flag}</span>} {airport.city}
              {airport.country && <span>, {airport.country}</span>}
            </p>
          </div>
          <button className="detail-close" type="button" onClick={onClose} aria-label="Close airport detail">
            ×
          </button>
        </header>

        <div className="detail-grid">
          <div className="info-tile">
            <span>📍 Region</span>
            <strong>{airport.region || "Not specified"}</strong>
          </div>
          <div className="info-tile">
            <span>🌍 Country</span>
            <strong>{airport.country}</strong>
          </div>
          <div className="info-tile">
            <span>🏷 Type</span>
            <strong>{typeLabel(airport.type)}</strong>
          </div>
          <div className="info-tile">
            <span>⭐ Priority Score</span>
            <strong>{airport.priority ?? 0}</strong>
          </div>
          <div className="info-tile">
            <span>🔤 IATA Code</span>
            <strong>{airport.iata}</strong>
          </div>
          <div className="info-tile">
            <span>📡 Matched via</span>
            <strong>{matchTypes.map((type) => MATCH_LABELS[type] ?? type).join(", ") || "Search"}</strong>
          </div>
        </div>

        <section className="detail-section">
          <h3>Also known as</h3>
          <div className="alias-strip">
            {aliases.length > 0 ? (
              aliases.map((alias) => <span key={alias}>{alias}</span>)
            ) : (
              <span>No aliases returned</span>
            )}
          </div>
        </section>

        {airport.is_multi_airport_city && subAirports.length > 0 && (
          <section className="detail-section">
            <h3>Airports in this city</h3>
            <div className="detail-sub-list">
              {subAirports.map((subAirport) => (
                <div key={subAirport.iata} className="detail-sub-card">
                  <span>{subAirport.iata}</span>
                  <strong>{subAirport.name}</strong>
                </div>
              ))}
            </div>
          </section>
        )}

      </aside>
    </div>
  );
}
