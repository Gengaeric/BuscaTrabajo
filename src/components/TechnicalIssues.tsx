import { useState } from 'react';
import type { TechnicalIssue } from '../types/jobOffer';

interface TechnicalIssuesProps {
  issues: TechnicalIssue[];
}

export function TechnicalIssues({ issues }: TechnicalIssuesProps) {
  const [copiedId, setCopiedId] = useState<string | null>(null);

  const copyIssue = async (issue: TechnicalIssue) => {
    const payload = JSON.stringify(issue, null, 2);
    await navigator.clipboard.writeText(payload);
    setCopiedId(issue.id);
    setTimeout(() => setCopiedId(null), 1200);
  };

  return (
    <section className="panel">
      <h2>Problemas técnicos detectados</h2>
      {issues.length === 0 ? (
        <p>No se detectaron problemas técnicos.</p>
      ) : (
        <div className="issues-list">
          {issues.map((issue) => (
            <article key={issue.id} className={`issue ${issue.severity}`}>
              <header>
                <strong>{issue.id}</strong>
                <span>{issue.severity.toUpperCase()}</span>
              </header>
              <ul>
                <li><b>Módulo:</b> {issue.module}</li>
                <li><b>Descripción técnica:</b> {issue.technicalDescription}</li>
                <li><b>Mensaje:</b> {issue.errorMessage}</li>
                <li><b>Stack:</b> {issue.stackTrace || '-'}</li>
                <li><b>Archivo/Función probable:</b> {issue.probableFileOrFunction}</li>
                <li><b>Posible causa:</b> {issue.possibleCause}</li>
                <li><b>Sugerencia:</b> {issue.suggestedFix}</li>
                <li><b>Fecha/hora:</b> {new Date(issue.occurredAt).toLocaleString('es-AR')}</li>
              </ul>
              <button type="button" onClick={() => copyIssue(issue)}>
                {copiedId === issue.id ? 'Copiado' : 'Copiar error completo'}
              </button>
            </article>
          ))}
        </div>
      )}
    </section>
  );
}
