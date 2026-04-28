# BuscaTrabajo (Paso 2)

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

---

## Script Python (Paso 2: base central de seguimiento)

Este repositorio también incluye un scraper independiente en Python para extraer ofertas públicas desde **Bumeran Argentina** y guardarlas en CSV.

### Estructura adicional

```txt
BuscaTrabajo/
  scraper.py
  requirements.txt
  data/
    offers.csv (base central, se genera al correr)
  storage.py (módulo de persistencia y seguimiento)
  logs/
    scraper.log (se genera al correr)
```

### Cómo instalar

```bash
python -m venv .venv
source .venv/bin/activate  # En Windows: .venv\Scripts\activate
pip install -r requirements.txt
python -m playwright install chromium
```

### Cómo correr

```bash
python scraper.py
```

### Qué hace

- Abre Bumeran Argentina.
- Ejecuta búsquedas públicas con keywords: `Recursos Humanos` y `HR`.
- Filtra por ubicación: `Buenos Aires`.
- Extrae (si están disponibles):
  - título
  - empresa
  - ubicación
  - link
  - fecha de publicación
- Limita resultados a un máximo de 25 ofertas.
- Usa `storage.py` para cargar, insertar/actualizar (`upsert`) y guardar ofertas normalizadas.
- Genera `id` único por oferta (hash SHA-256 del `link`).
- Evita duplicados por `id`.
- Si una oferta ya existe, conserva campos de seguimiento (`status`, `notes`, `score`, `category`, `action_required`, `manual_required`, `manual_reason`).
- Guarda resultados en `data/offers.csv`.
- Guarda logs en `logs/scraper.log`.
- Si no encuentra elementos o hay errores puntuales, los registra y continúa sin romper la ejecución.

### Cómo ver resultados

- CSV: `data/offers.csv`
- Logs: `logs/scraper.log`



### Esquema de la base central (`data/offers.csv`)

Cada fila se guarda con este esquema extensible:

- `id`
- `title`
- `company`
- `location`
- `link`
- `source`
- `scraped_at`
- `status`
- `score`
- `category`
- `action_required`
- `notes`
- `manual_required`
- `manual_reason`

### Flujo al ejecutar `python scraper.py`

1. Carga ofertas existentes desde `data/offers.csv`.
2. Scrapea nuevas ofertas públicas desde Bumeran.
3. Para cada oferta, calcula `id` desde `link` y hace `upsert`:
   - si no existe, la agrega,
   - si existe, actualiza datos de scraping y preserva seguimiento manual.
4. Guarda todo nuevamente en la base central CSV sin duplicados.
