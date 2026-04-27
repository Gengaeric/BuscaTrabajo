export type SearchMode = 'mock' | 'real';

export interface SearchCriteria {
  keywords: string;
  location: string;
  maxResults: number;
  mode: SearchMode;
}

export interface JobOffer {
  id: string;
  title: string;
  company: string;
  location: string;
  modality?: string;
  salary?: string;
  postedDate?: string;
  description?: string;
  url: string;
  source: 'Bumeran';
  scrapedAt: string;
  status: 'active' | 'unknown' | 'requires_review';
}

export interface TechnicalIssue {
  id: string;
  module: string;
  severity: 'low' | 'medium' | 'high';
  technicalDescription: string;
  errorMessage: string;
  stackTrace?: string;
  probableFileOrFunction: string;
  possibleCause: string;
  suggestedFix: string;
  occurredAt: string;
  raw?: string;
}

export interface SearchResponse {
  success: boolean;
  mode: SearchMode;
  source: 'Bumeran';
  offers: JobOffer[];
  issues: TechnicalIssue[];
  logs: string[];
  extractedAt: string;
}
