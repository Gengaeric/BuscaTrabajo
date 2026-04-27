import type { Handler } from '@netlify/functions';
import { readFile } from 'node:fs/promises';
import { resolve } from 'node:path';
import { normalizeOffers } from '../../scrapers/bumeran/normalizer';
import { scrapeBumeranReal } from '../../scrapers/bumeran/scraper';
import type { SearchCriteria, SearchResponse, TechnicalIssue } from '../../src/types/jobOffer';

function makeIssue(partial: Omit<TechnicalIssue, 'id' | 'occurredAt'>): TechnicalIssue {
  return {
    id: `issue-${Date.now()}-${Math.round(Math.random() * 999)}`,
    occurredAt: new Date().toISOString(),
    ...partial
  };
}

async function loadMockOffers(maxResults: number) {
  const filePath = resolve(process.cwd(), 'data/mockOffers.json');
  const raw = await readFile(filePath, 'utf8');
  const parsed = JSON.parse(raw) as Array<Record<string, string | null>>;
  return normalizeOffers(parsed, new Date().toISOString()).slice(0, maxResults);
}

export const handler: Handler = async (event) => {
  const logs: string[] = [];
  const issues: TechnicalIssue[] = [];

  if (event.httpMethod !== 'POST') {
    return { statusCode: 405, body: JSON.stringify({ error: 'Method not allowed' }) };
  }

  let criteria: SearchCriteria;
  try {
    criteria = JSON.parse(event.body || '{}') as SearchCriteria;
  } catch {
    return { statusCode: 400, body: JSON.stringify({ error: 'JSON inválido' }) };
  }

  const normalizedCriteria: SearchCriteria = {
    keywords: criteria.keywords || '',
    location: criteria.location || '',
    maxResults: Math.min(Math.max(Number(criteria.maxResults) || 10, 1), 50),
    mode: criteria.mode === 'real' ? 'real' : 'mock'
  };

  logs.push(`[${new Date().toISOString()}] search-bumeran iniciado en modo ${normalizedCriteria.mode}.`);

  let offers = [] as SearchResponse['offers'];

  if (normalizedCriteria.mode === 'mock') {
    offers = await loadMockOffers(normalizedCriteria.maxResults);
    logs.push(`[${new Date().toISOString()}] Datos mock cargados: ${offers.length}.`);
  } else {
    try {
      const real = await scrapeBumeranReal(normalizedCriteria);
      offers = real.offers;
      logs.push(...real.logs);

      if (offers.length === 0) {
        issues.push(
          makeIssue({
            module: 'scrapers/bumeran/scraper.ts',
            severity: 'medium',
            technicalDescription: 'Scraper ejecutado sin resultados.',
            errorMessage: 'No se encontraron ofertas bajo los selectores actuales.',
            stackTrace: undefined,
            probableFileOrFunction: 'scrapeBumeranReal()',
            possibleCause: 'Cambios en el DOM de Bumeran o filtros demasiado restrictivos.',
            suggestedFix: 'Actualizar selectores y validar manualmente en navegador.',
            raw: JSON.stringify({ criteria: normalizedCriteria })
          })
        );
      }
    } catch (error) {
      const message = error instanceof Error ? error.message : 'Error desconocido en scraping real';
      issues.push(
        makeIssue({
          module: 'netlify/functions/search-bumeran.ts',
          severity: 'high',
          technicalDescription: 'Falló el modo real y se activó fallback automático a mock.',
          errorMessage: message,
          stackTrace: error instanceof Error ? error.stack : undefined,
          probableFileOrFunction: 'handler() / scrapeBumeranReal()',
          possibleCause:
            'Playwright no está disponible en Netlify Function o Bumeran bloqueó el acceso (captcha/rate limit).',
          suggestedFix:
            'Probar scraping real en ejecución local/servicio externo y mantener mock en Netlify para continuidad.',
          raw: JSON.stringify(error)
        })
      );

      offers = await loadMockOffers(normalizedCriteria.maxResults);
      logs.push(`[${new Date().toISOString()}] Fallback a mock ejecutado por error en modo real.`);
    }
  }

  const payload: SearchResponse = {
    success: true,
    source: 'Bumeran',
    mode: normalizedCriteria.mode,
    offers,
    issues,
    logs,
    extractedAt: new Date().toISOString()
  };

  return {
    statusCode: 200,
    headers: { 'content-type': 'application/json' },
    body: JSON.stringify(payload)
  };
};
