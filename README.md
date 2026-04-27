# BuscaTrabajo (Paso 1)

Dashboard web para buscar ofertas públicas en **Bumeran Argentina** con arquitectura preparada para futuras fuentes.

> Este paso **no postula**, **no inicia sesión**, **no completa formularios** y **no envía datos personales**. Solo consulta información pública.

## Stack
- Frontend: React + Vite
- Deploy: Netlify
- API backend: Netlify Functions
- Scraper real: Playwright (`playwright-core`)
- Fallback: modo `mock` con `data/mockOffers.json`

## Estructura

```txt
src/
  components/
    SearchForm.tsx
    ResultsTable.tsx
    StatusCards.tsx
    TechnicalIssues.tsx
  services/
    apiClient.ts
  types/
    jobOffer.ts
netlify/
  functions/
    search-bumeran.ts
scrapers/
  bumeran/
    scraper.ts
    normalizer.ts
data/
  mockOffers.json
```

## Instalación local
```bash
npm install
```

## Ejecución local
### Opción recomendada (simula Netlify Functions)
```bash
npx netlify dev
```
Abre `http://localhost:8888`.

### Opción frontend sola
```bash
npm run dev:vite
```
Abre `http://localhost:5173`.

## Build
```bash
npm run build
```

## Deploy en Netlify
1. Subir este repo a GitHub.
2. Entrar a Netlify y elegir **Add new site > Import an existing project**.
3. Conectar GitHub y seleccionar el repo.
4. Configuración sugerida (ya está en `netlify.toml`):
   - Build command: `npm run build`
   - Publish directory: `dist`
   - Functions directory: `netlify/functions`
5. Deploy.

## Conectar GitHub con Netlify
1. Autorizar Netlify sobre GitHub.
2. Elegir branch principal (ej: `main`).
3. Activar deploy automático en cada push.

## Probar modo mock
1. Abrir la app.
2. Elegir modo `mock`.
3. Completar criterios.
4. Click en **Buscar en Bumeran**.
5. Ver resultados en tabla + logs + sección de problemas técnicos.

## Probar modo real
1. Elegir modo `real`.
2. Ejecutar búsqueda.
3. Si el scraping funciona, devuelve resultados reales normalizados.
4. Si falla, la función retorna error estructurado y hace fallback automático a `mock`.

## Limitaciones de Playwright en Netlify Functions
- Entornos serverless pueden no incluir navegador Chromium listo para ejecutar.
- Límites de tiempo/memoria pueden cortar scrapes extensos.
- Sitios con anti-bot/captcha pueden bloquear ejecución automática.

## Qué hacer si Playwright falla en Netlify
1. Mantener el dashboard activo con modo `mock`.
2. Ejecutar scraping real en:
   - entorno local programado, o
   - servicio externo dedicado (worker/cron/server).
3. Exponer ese scraper vía API y reutilizar el mismo normalizador y tipos.

## Cómo agregar otra fuente en el futuro
1. Crear carpeta `scrapers/nueva-fuente/` con `scraper.ts` + `normalizer.ts`.
2. Mantener formato de salida `JobOffer` en `src/types/jobOffer.ts`.
3. Crear función Netlify adicional (`netlify/functions/search-nueva-fuente.ts`).
4. Añadir opción en UI para seleccionar fuente y consumir el endpoint correspondiente.

## Seguridad y límites implementados
- Sin login.
- Sin postulación.
- Sin envío de datos personales.
- Sin bypass de captcha.
- Si aparece bloqueo/captcha: error explícito `requiere revisión técnica/manual`.
