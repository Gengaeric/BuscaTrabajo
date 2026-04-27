import type { SearchCriteria, SearchResponse } from '../types/jobOffer';

export async function searchBumeran(criteria: SearchCriteria): Promise<SearchResponse> {
  const response = await fetch('/.netlify/functions/search-bumeran', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(criteria)
  });

  if (!response.ok) {
    const text = await response.text();
    throw new Error(`Error HTTP ${response.status}: ${text}`);
  }

  return (await response.json()) as SearchResponse;
}
