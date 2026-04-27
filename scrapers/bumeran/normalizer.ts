import { createHash } from 'node:crypto';
import type { JobOffer } from '../../src/types/jobOffer';

interface RawOffer {
  title?: string | null;
  company?: string | null;
  location?: string | null;
  modality?: string | null;
  salary?: string | null;
  postedDate?: string | null;
  description?: string | null;
  url?: string | null;
}

export function normalizeOffers(rawOffers: RawOffer[], scrapedAt: string): JobOffer[] {
  const seen = new Set<string>();
  const normalized: JobOffer[] = [];

  for (const raw of rawOffers) {
    const url = (raw.url || '').trim();
    if (!url) {
      continue;
    }

    const uniqueKey = url || `${raw.title || ''}-${raw.company || ''}`;
    const id = createHash('sha1').update(uniqueKey).digest('hex').slice(0, 16);

    if (seen.has(id)) {
      continue;
    }
    seen.add(id);

    normalized.push({
      id,
      title: raw.title?.trim() || 'Sin título',
      company: raw.company?.trim() || 'Empresa no informada',
      location: raw.location?.trim() || 'Ubicación no informada',
      modality: raw.modality?.trim() || undefined,
      salary: raw.salary?.trim() || undefined,
      postedDate: raw.postedDate?.trim() || undefined,
      description: raw.description?.trim() || undefined,
      url,
      source: 'Bumeran',
      scrapedAt,
      status: 'active'
    });
  }

  return normalized;
}
