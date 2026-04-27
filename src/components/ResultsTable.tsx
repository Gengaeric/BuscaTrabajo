import type { JobOffer } from '../types/jobOffer';

interface ResultsTableProps {
  offers: JobOffer[];
}

export function ResultsTable({ offers }: ResultsTableProps) {
  return (
    <section className="panel">
      <h2>Resultados</h2>
      <div className="table-wrap">
        <table>
          <thead>
            <tr>
              <th>Título</th>
              <th>Empresa</th>
              <th>Ubicación</th>
              <th>Modalidad</th>
              <th>Salario</th>
              <th>Publicación</th>
              <th>Link</th>
              <th>Fuente</th>
              <th>Extracción</th>
            </tr>
          </thead>
          <tbody>
            {offers.length === 0 ? (
              <tr>
                <td colSpan={9}>Sin resultados todavía.</td>
              </tr>
            ) : (
              offers.map((offer) => (
                <tr key={offer.id}>
                  <td>{offer.title}</td>
                  <td>{offer.company}</td>
                  <td>{offer.location}</td>
                  <td>{offer.modality || '-'}</td>
                  <td>{offer.salary || '-'}</td>
                  <td>{offer.postedDate || '-'}</td>
                  <td>
                    <a href={offer.url} target="_blank" rel="noreferrer">
                      Ver oferta
                    </a>
                  </td>
                  <td>{offer.source}</td>
                  <td>{new Date(offer.scrapedAt).toLocaleString('es-AR')}</td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>
    </section>
  );
}
