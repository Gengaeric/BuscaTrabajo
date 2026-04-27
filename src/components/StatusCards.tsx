interface StatusCardsProps {
  offers: number;
  source: string;
  errors: number;
  lastScraping: string;
}

export function StatusCards({ offers, source, errors, lastScraping }: StatusCardsProps) {
  const cards = [
    { label: 'Ofertas encontradas', value: offers.toString(), tone: 'ok' },
    { label: 'Fuente activa', value: source, tone: 'info' },
    { label: 'Errores', value: errors.toString(), tone: errors > 0 ? 'danger' : 'ok' },
    { label: 'Último scraping', value: lastScraping || '-', tone: 'muted' }
  ];

  return (
    <section className="cards-grid">
      {cards.map((card) => (
        <article key={card.label} className={`card ${card.tone}`}>
          <p>{card.label}</p>
          <strong>{card.value}</strong>
        </article>
      ))}
    </section>
  );
}
