import { chromium } from 'playwright-core';
import { normalizeOffers } from './normalizer';
import type { JobOffer } from '../../src/types/jobOffer';

interface ScraperInput {
  keywords: string;
  location: string;
  maxResults: number;
}

interface ScraperResult {
  offers: JobOffer[];
  logs: string[];
}

export async function scrapeBumeranReal(input: ScraperInput): Promise<ScraperResult> {
  const logs: string[] = [];
  const scrapedAt = new Date().toISOString();
  const search = new URL('https://www.bumeran.com.ar/empleos-busqueda.html');

  if (input.keywords) {
    search.searchParams.set('palabra', input.keywords);
  }
  if (input.location) {
    search.searchParams.set('location', input.location);
  }

  logs.push(`[${scrapedAt}] Abriendo URL de búsqueda: ${search.toString()}`);

  const browser = await chromium.launch({
    headless: true,
    args: ['--no-sandbox', '--disable-setuid-sandbox']
  });

  try {
    const page = await browser.newPage();
    await page.goto(search.toString(), { waitUntil: 'domcontentloaded', timeout: 45_000 });

    const captchaHint = await page
      .locator('text=captcha, text=verificación, text=robot')
      .first()
      .isVisible()
      .catch(() => false);

    if (captchaHint) {
      throw new Error('Bumeran muestra captcha o bloqueo anti-bot. Requiere revisión técnica/manual.');
    }

    await page.waitForTimeout(1500);
    const rawOffers = await page.evaluate((maxResults: number) => {
      const cards = Array.from(document.querySelectorAll('article, [data-testid="job-card"], .scaffold-layout__list-item'));
      return cards.slice(0, maxResults).map((card) => {
        const titleEl = card.querySelector('h2, h3, a');
        const companyEl = card.querySelector('[class*=company], [data-testid*=company]');
        const locationEl = card.querySelector('[class*=location], [data-testid*=location]');
        const modalityEl = card.querySelector('[class*=modality], [data-testid*=modality]');
        const salaryEl = card.querySelector('[class*=salary], [data-testid*=salary]');
        const dateEl = card.querySelector('time, [class*=date], [data-testid*=date]');
        const descEl = card.querySelector('p');
        const linkEl = card.querySelector('a[href*="bumeran.com.ar"]') as HTMLAnchorElement | null;

        return {
          title: titleEl?.textContent ?? null,
          company: companyEl?.textContent ?? null,
          location: locationEl?.textContent ?? null,
          modality: modalityEl?.textContent ?? null,
          salary: salaryEl?.textContent ?? null,
          postedDate: dateEl?.textContent ?? null,
          description: descEl?.textContent ?? null,
          url: linkEl?.href ?? null
        };
      });
    }, input.maxResults);

    const offers = normalizeOffers(rawOffers, scrapedAt).slice(0, input.maxResults);
    logs.push(`[${new Date().toISOString()}] Ofertas normalizadas: ${offers.length}`);

    return { offers, logs };
  } finally {
    await browser.close();
  }
}
