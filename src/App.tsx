import { useMemo, useState } from 'react';
import { SearchForm } from './components/SearchForm';
import { ResultsTable } from './components/ResultsTable';
import { StatusCards } from './components/StatusCards';
import { TechnicalIssues } from './components/TechnicalIssues';
import { searchBumeran } from './services/apiClient';
import type { JobOffer, SearchCriteria, SearchResponse, TechnicalIssue } from './types/jobOffer';

const initialCriteria: SearchCriteria = {
  keywords: 'developer',
  location: 'Argentina',
  maxResults: 10,
  mode: 'mock'
};

function App() {
  const [criteria, setCriteria] = useState<SearchCriteria>(initialCriteria);
  const [offers, setOffers] = useState<JobOffer[]>([]);
  const [issues, setIssues] = useState<TechnicalIssue[]>([]);
  const [logs, setLogs] = useState<string[]>([]);
  const [loading, setLoading] = useState(false);
  const [lastScraping, setLastScraping] = useState('');
  const [source, setSource] = useState('Bumeran');

  const runSearch = async () => {
    setLoading(true);
    setLogs((prev) => [...prev, `[${new Date().toISOString()}] Ejecutando búsqueda (${criteria.mode})...`]);
    try {
      const data: SearchResponse = await searchBumeran(criteria);
      setOffers(data.offers);
      setIssues(data.issues);
      setLogs((prev) => [...prev, ...data.logs]);
      setLastScraping(data.extractedAt);
      setSource(data.source);
    } catch (error) {
      const message = error instanceof Error ? error.message : 'Error desconocido';
      setIssues((prev) => [
        ...prev,
        {
          id: `frontend-${Date.now()}`,
          module: 'src/services/apiClient',
          severity: 'high',
          technicalDescription: 'Fallo al invocar Netlify Function.',
          errorMessage: message,
          stackTrace: error instanceof Error ? error.stack : undefined,
          probableFileOrFunction: 'searchBumeran()',
          possibleCause: 'La función no está disponible o devolvió un error HTTP.',
          suggestedFix: 'Verificar netlify dev/build y revisar logs de función.',
          occurredAt: new Date().toISOString(),
          raw: JSON.stringify(error)
        }
      ]);
    } finally {
      setLoading(false);
    }
  };

  const statusLastScraping = useMemo(
    () => (lastScraping ? new Date(lastScraping).toLocaleString('es-AR') : '-'),
    [lastScraping]
  );

  return (
    <main className="container">
      <header className="title-wrap">
        <h1>BuscaTrabajo</h1>
        <p>Dashboard de búsqueda para fuentes públicas (Paso 1: Bumeran Argentina).</p>
      </header>

      <StatusCards offers={offers.length} source={source} errors={issues.length} lastScraping={statusLastScraping} />
      <SearchForm criteria={criteria} loading={loading} onChange={setCriteria} onSubmit={runSearch} />
      <ResultsTable offers={offers} />
      <TechnicalIssues issues={issues} />

      <section className="panel">
        <h2>Logs / Estado</h2>
        <div className="logs">
          {logs.length === 0 ? <p>Sin logs todavía.</p> : logs.map((log, index) => <p key={`${log}-${index}`}>{log}</p>)}
        </div>
      </section>
    </main>
  );
}

export default App;
