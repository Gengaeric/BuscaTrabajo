import type { SearchCriteria } from '../types/jobOffer';

interface SearchFormProps {
  criteria: SearchCriteria;
  loading: boolean;
  onChange: (criteria: SearchCriteria) => void;
  onSubmit: () => void;
}

export function SearchForm({ criteria, loading, onChange, onSubmit }: SearchFormProps) {
  return (
    <section className="panel">
      <h2>Criterios de búsqueda</h2>
      <div className="grid-form">
        <label>
          Palabras clave
          <input
            value={criteria.keywords}
            onChange={(event) => onChange({ ...criteria, keywords: event.target.value })}
            placeholder="Ej: Frontend React"
          />
        </label>

        <label>
          Ubicación
          <input
            value={criteria.location}
            onChange={(event) => onChange({ ...criteria, location: event.target.value })}
            placeholder="Ej: CABA"
          />
        </label>

        <label>
          Cantidad máxima de resultados
          <input
            type="number"
            min={1}
            max={50}
            value={criteria.maxResults}
            onChange={(event) =>
              onChange({ ...criteria, maxResults: Math.max(1, Number(event.target.value) || 1) })
            }
          />
        </label>

        <label>
          Modo de búsqueda
          <select
            value={criteria.mode}
            onChange={(event) =>
              onChange({ ...criteria, mode: event.target.value as SearchCriteria['mode'] })
            }
          >
            <option value="mock">mock</option>
            <option value="real">real</option>
          </select>
        </label>
      </div>

      <button disabled={loading} onClick={onSubmit} className="primary-btn" type="button">
        {loading ? 'Buscando...' : 'Buscar en Bumeran'}
      </button>
    </section>
  );
}
