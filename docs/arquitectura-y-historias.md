# EasyHome — Documentación de arquitectura e historias de usuario

> Plataforma web que centraliza avisos inmobiliarios de Mendoza (venta y alquiler)
> y los clasifica automáticamente según su **nivel de accesibilidad para personas
> con movilidad reducida**, usando IA para analizar texto e imágenes.

---

## 1. Visión general del producto

EasyHome resuelve un problema concreto: los portales inmobiliarios tradicionales
no permiten filtrar por accesibilidad. Una persona en silla de ruedas, un adulto
mayor o alguien en rehabilitación no tiene forma de saber si una vivienda tiene
rampa, ascensor, baño adaptado, etc., sin leer cada aviso uno por uno.

EasyHome:
1. **Recolecta** avisos de 3 fuentes (ZonaProp, MendozaProp, Argenprop) automáticamente.
2. **Deduplica** la misma propiedad publicada en varias fuentes.
3. **Analiza** cada propiedad con IA: NLP sobre la descripción + visión sobre las fotos.
4. **Puntúa** la accesibilidad (score 0-10 + nivel) según los criterios detectados.
5. **Publica** un buscador con filtros por accesibilidad, y permite a la comunidad
   votar/corregir los criterios.
6. **Administra** todo desde un panel: métricas, scrapers, re-análisis, moderación.

### Actores del sistema
- **Visitante**: navega y filtra propiedades sin cuenta.
- **Usuario registrado**: además vota criterios, comenta, guarda favoritos, configura preferencias, reporta avisos.
- **Administrador** (`emilianomassolin@gmail.com`): panel completo de gestión.
- **Sistema** (scheduler + IA): scraping y análisis automáticos.

---

## 2. Arquitectura

### 2.1 Diagrama de componentes

```
                          ┌──────────────────────────┐
       Usuario  ───────►  │   Vercel (frontend SPA)   │
                          │   React 19 + Vite + TW    │
                          └────────────┬─────────────┘
                                       │  (reverse proxy: /api/* → tunnel)
                                       ▼
                          ┌──────────────────────────┐
                          │   Cloudflare Tunnel       │  URL pública estable
                          │   (*.trycloudflare.com)   │  auto-actualizada por systemd
                          └────────────┬─────────────┘
                                       ▼
   ┌───────────────────────────────────────────────────────────────────┐
   │                     VM (OpenStack) · systemd                        │
   │                                                                     │
   │   ┌─────────────────────────┐      ┌──────────────────────────┐    │
   │   │  uvicorn / FastAPI       │      │  APScheduler (in-process) │    │
   │   │  - API pública (/api)    │◄────►│  CronTrigger 03:00 ART    │    │
   │   │  - API admin (/api/admin)│      │  → scraping diario        │    │
   │   │  - Auth (JWT)            │      └──────────────────────────┘    │
   │   │  - sirve frontend (dist) │                                       │
   │   └────────┬─────────────────┘                                       │
   │            │                                                         │
   │   ┌────────▼─────────┐   ┌──────────────┐   ┌──────────────────┐     │
   │   │  PostgreSQL      │   │ FlareSolverr │   │  Scrapers        │     │
   │   │  + pg_trgm       │   │ (Docker)     │◄──┤  ZP / MP / AP    │     │
   │   └──────────────────┘   │ bypass CF    │   └──────────────────┘     │
   │                          └──────────────┘                           │
   └───────────────────────────────────────────────────────────────────┘
                                       │
              ┌────────────────────────┴────────────────────────┐
              ▼                                                  ▼
   ┌────────────────────────┐                      ┌──────────────────────────┐
   │  API NLP universidad   │                      │  Anthropic API (Claude)  │
   │  gemma4-e2b (texto +   │                      │  claude-sonnet-4-6       │
   │  scoring de fotos)     │                      │  (visión de imágenes)    │
   └────────────────────────┘                      └──────────────────────────┘
```

### 2.2 Flujo de datos principal

**Ingesta (diaria o manual):**
```
Scraper → parse HTML → dedup (pg_trgm) → INSERT/UPDATE Property → marca inactivas
       → snapshot de métricas
```

**Análisis de accesibilidad (por propiedad):**
```
keyword_filter (¿menciona accesibilidad?)
   │  no → resultado vacío (no gasta IA)
   ▼  sí
NLP (gemma) sobre descripción → criterios de texto
   │  sin criterios → no manda fotos a visión
   ▼  con criterios
Visión: gemma puntúa cada foto → top 3 → Claude analiza → criterios de imagen
   ▼
calcular_score(texto, visión, título, override_comunidad) → score 0-10 + nivel
```

**Presentación:**
```
GET /api/properties (filtros) → solo activa=true, duplicate_of=null → SPA
```

---

## 3. Stack tecnológico

| Capa | Tecnología | Detalle |
|------|-----------|---------|
| **Frontend** | React 19, Vite 8, Tailwind CSS 4 | SPA. SSE (`EventSource`) para progreso en vivo de scrapers/análisis. Gráfico de líneas SVG propio (`SimpleLineChart`). |
| **Backend** | Python, FastAPI, Uvicorn, Pydantic | API REST + sirve el `dist/` del frontend como fallback. |
| **ORM / DB** | SQLAlchemy 2.0, PostgreSQL, `psycopg2` | Extensión `pg_trgm` para similitud difusa de texto en la deduplicación. JSONB para resultados de IA. |
| **Scraping** | BeautifulSoup4, requests, FlareSolverr | FlareSolverr (Docker, puerto 8191) hace bypass del anti-bot Cloudflare de ZonaProp. |
| **IA — texto** | API universidad `gemma4-e2b` | Detecta criterios en la descripción y puntúa relevancia de fotos. |
| **IA — visión** | Anthropic `claude-sonnet-4-6` (SDK `anthropic`) | Analiza las fotos top y detecta criterios visuales. |
| **Auth** | `python-jose` (JWT), `passlib`+`bcrypt` | Token de 7 días. Admin por email. |
| **Scheduler** | APScheduler `CronTrigger` | Scraping diario 06:00 UTC (03:00 ART). |
| **Infra** | OpenStack VM, systemd, Cloudflare Tunnel, Vercel, ZeroTier | Servicios `easyhome` y `cloudflared`. Script systemd que actualiza la URL del tunnel en Vercel al reiniciar. |
| **Testing/calidad** | pytest (102 tests), ESLint | |

---

## 4. Modelo de datos

Tablas (SQLAlchemy en `backend/database/models.py`):

### `properties` — núcleo
| Campo | Tipo | Notas |
|-------|------|-------|
| `id` | int PK | |
| `ml_id` | str único | id en la fuente origen |
| `titulo`, `descripcion`, `ubicacion` | str/text | |
| `precio` | float | |
| `permalink_ml` | str | link al aviso original |
| `fotos_urls` | JSONB | lista de URLs |
| `fuente` | str | zonaprop / mendozaprop / argenprop |
| `tipo_operacion` | str | venta / alquiler |
| `activa` | bool | false cuando deja de aparecer en la fuente |
| `superficie_m2`, `ambientes` | float/int | extraídos de la descripción (para dedup) |
| `duplicate_of` | FK→properties | apunta a la propiedad canónica si es duplicado |
| `nlp_resultado`, `vision_resultado` | JSONB | criterios detectados por IA |
| `score_accesibilidad` | float | 0-10 |
| `justificacion_score` | text | explicación legible |
| `confianza_general` | float | |
| `manual_override` | JSONB | correcciones de la comunidad por criterio |
| `analizado` | bool | |
| `fecha_creacion`, `fecha_actualizacion`, `fecha_analisis` | datetime | |

### `users`, `user_preferences`, `favorites`
Cuentas, preferencias de búsqueda (criterios, zona, operación, rango de precio) y favoritos.

### `comentarios`, `votos_criterios`
- `comentarios`: comentarios de usuarios por propiedad (soft-delete con `activo`).
- `votos_criterios`: voto sí/no de cada usuario por criterio y propiedad (unique `property_id+user_id+criterio`). Al llegar a un umbral de votos coincidentes se aplica `manual_override` y se recalcula el score.

### `reports`
Reportes de usuarios (motivo, descripción, estado pendiente/resuelto/ignorado) para moderación.

### `scraper_logs`
Historial de cada corrida de scraper (fuente, inicio, fin, estado, cantidad, error). Lo escriben **tanto las corridas manuales como las automáticas**.

### `snapshots_propiedades`
Métrica histórica: por fecha, fuente y tipo de operación, cuántas propiedades activas hay. Tiene la bandera `solo_accesibles` para distinguir la serie total de la serie "solo accesibles" (score > 0). Alimenta el Timeline.

---

## 5. Módulos del backend

```
backend/
├── main.py                 # app FastAPI, CORS, monta routers + sirve frontend
├── api/
│   ├── routes.py           # API pública (propiedades, comentarios, votos)
│   ├── admin_routes.py     # API admin (dashboard, scrapers, análisis, timeline...)
│   ├── auth_routes.py      # registro, login, recuperación
│   └── user_routes.py      # favoritos, preferencias, reportes
├── scrapers/
│   ├── zonaprop_scraper.py     # usa FlareSolverr
│   ├── mendozaprop_scraper.py
│   ├── argenprop_scraper.py
│   ├── dedup_utils.py          # find_canonical() con pg_trgm
│   └── extract_utils.py        # extrae m²/ambientes de la descripción
├── nlp/
│   ├── keyword_filter.py   # pre-filtro: ¿vale la pena llamar a la IA?
│   └── analyzer.py         # llama a gemma sobre la descripción
├── vision/
│   └── image_analyzer.py   # gemma puntúa fotos → Claude analiza top 3
├── scoring/
│   └── calculator.py       # combina texto+visión → score, nivel, justificación
├── scheduler/
│   └── jobs.py             # CronTrigger diario + snapshots
├── core/
│   └── security.py         # JWT, hashing
└── database/
    ├── models.py
    └── connection.py
```

### 5.1 Lógica de scoring (`scoring/calculator.py`)
- **8 criterios**: rampa, ascensor, baño adaptado, entrada ancha, estacionamiento adaptado, ducha a nivel de piso, pasamanos, planta baja.
- **Score** = (criterios detectados aplicables / criterios aplicables) × 10.
- **Criterios excluidos por tipo**: una cochera o terreno no necesita ascensor ni baño adaptado, así que se excluyen del denominador (`CRITERIOS_EXCLUIDOS`). El tipo se infiere del título.
- **Niveles**: ≥8.5 Muy accesible · ≥6 Accesible · ≥3.5 Parcialmente accesible · resto Poco accesible.
- **Override comunitario**: los votos pueden sumar/quitar criterios antes de calcular.
- **Confianza**: 0.6 × confianza_texto + 0.4 × (0.8 si hubo visión, si no 0.3).

### 5.2 Deduplicación (`scrapers/dedup_utils.py`)
Antes de insertar una propiedad nueva, busca una canónica existente comparando con `pg_trgm`:
- Similitud de dirección ≥ 0.80, **o** ≥ 0.65 si además coinciden superficie (±15%) y/o ambientes.
- Si la encuentra, marca la nueva con `duplicate_of`. La API siempre filtra `duplicate_of IS NULL`.

### 5.3 Análisis en cascada (ahorro de costos)
1. `keyword_filter`: si la descripción no menciona ninguna palabra de accesibilidad → resultado vacío, **no gasta IA**.
2. NLP (`gemma`) sobre la descripción.
3. Visión **solo si** el texto detectó algo: `gemma` puntúa cada foto, se quedan las 3 mejores (score ≥ 3), y solo esas van a Claude.

---

## 6. API REST (inventario)

### Pública — `/api`
| Método | Ruta | Descripción |
|--------|------|-------------|
| GET | `/health` | healthcheck |
| GET | `/stats` | totales (propiedades, con accesibilidad) |
| GET | `/properties` | listado con filtros (fuente, score, operación, zona, tipo, criterios, orden, paginación) |
| GET | `/properties/{id}` | detalle |
| POST | `/analyze/{id}` | analiza una propiedad puntual |
| GET/POST/DELETE | `/properties/{id}/comments`, `/comments/{id}` | comentarios (POST/DELETE requieren login) |
| GET | `/properties/{id}/votos_criterios` | conteo de votos por criterio |
| POST | `/properties/{id}/votar_criterio` | votar (login) |
| DELETE | `/properties/{id}/votos_criterios/{criterio}` | quitar voto (login) |

### Auth — `/api/auth`
`register`, `login`, `me`, `forgot-password`, `reset-password`.

### Usuario — `/api/user`
`preferences` (GET/PUT), `favorites` (GET, ids, POST/DELETE por id), `reports` (POST, GET propios).

### Admin — `/api/admin` (requiere token admin o JWT del admin)
`dashboard`, `properties` (+export CSV, reanalyze, status, accessibility), `reports` (GET/POST/PATCH),
`scrapers/{fuente}/run` + `scrapers/{run_id}/stream` (SSE) + `scrapers/logs` (GET/DELETE),
`analysis/start` + `analysis/{run_id}/stream` (SSE) + `analysis/status`,
`users` (GET, status), `timeline`, `comments` (moderación).

---

## 7. Frontend

```
frontend/src/
├── App.jsx                 # buscador principal + filtros
├── api.js / authApi.js / adminApi.js   # clientes fetch
├── context/AuthContext.jsx # sesión, token, favoritos
├── components/
│   ├── PropertyCard.jsx    # tarjeta de propiedad
│   ├── PropertyModal.jsx   # detalle (fotos, criterios, comentarios, votación)
│   ├── ScoreBar.jsx        # barra de score con color por nivel
│   ├── LoginModal.jsx
│   └── ProfileModal.jsx
└── pages/
    ├── AdminPanel.jsx       # panel admin (7 tabs)
    └── FavoritesPage.jsx
```

- **Búsqueda**: filtros por operación, tipo, zona, fuente, score mínimo, criterios, orden (↑ Score = más accesibles primero).
- **Panel admin (tabs)**: Dashboard · Propiedades · Reportes · Scrapers · Análisis · Usuarios · Timeline.
- **Tiempo real**: Scrapers y Análisis muestran progreso vía SSE; el re-análisis bloquea corridas concurrentes y se re-engancha al stream si recargás.
- **Timeline**: gráfico de líneas con granularidad Día/Semana/Mes/Año, toggle Todas/Solo accesibles, forward-fill de períodos sin datos.

---

## 8. Infraestructura y despliegue

- **VM OpenStack** corre `easyhome.service` (uvicorn) y `cloudflared.service` (tunnel), ambos con `Restart=always`.
- **Cloudflare Tunnel** expone la VM. Como la URL del quick tunnel cambia al reiniciar, un servicio systemd (`update-tunnel-url`) detecta la nueva URL al bootear y actualiza `vercel.json` vía API de GitHub → Vercel redespliega solo.
- **Vercel** hostea el frontend y actúa de reverse proxy (`/api/*` → tunnel actual).
- **`deploy.sh`**: rsync del backend a la VM + build y copia del frontend + `systemctl restart` + push a GitHub (dispara deploy de Vercel).
- **Scraping diario** vía APScheduler dentro del proceso (no cron del SO).

---

## 9. Historias de usuario

Formato del tablero: *"Como [rol], quiero [acción], para [beneficio]"* + criterios de aceptación.

### Épica A — Búsqueda y descubrimiento

**A1. Como visitante, quiero filtrar propiedades por nivel de accesibilidad, operación, zona, tipo y características, para encontrar viviendas que se adapten a mi movilidad.**
- Filtros: operación (venta/alquiler), tipo, departamento de Mendoza, fuente, score mínimo, criterios específicos.
- Orden por score ↑ (más accesibles primero) / ↓.
- Paginación. Si no hay resultados, mensaje "Sin resultados".

**A2. Como visitante, quiero ver el detalle de una propiedad con su score y criterios, para evaluarla antes de contactar.**
- Score numérico + nivel + justificación legible.
- Criterios detectados (texto / imagen / comunidad), galería de fotos, precio, ubicación, link al aviso original.

### Épica B — Análisis de accesibilidad con IA

**B1. Como sistema, quiero pre-filtrar por palabras clave antes de llamar a la IA, para no gastar tokens en avisos sin señales de accesibilidad.**

**B2. Como sistema, quiero analizar la descripción con NLP, para detectar criterios mencionados en el texto.**

**B3. Como sistema, quiero seleccionar y analizar las mejores fotos con visión por IA cuando el texto sugiere accesibilidad, para confirmar criterios visuales.**
- Solo se mandan a Claude las top 3 fotos con score de relevancia ≥ 3.

**B4. Como sistema, quiero combinar texto + imágenes en un score 0-10 ponderado y excluir criterios no aplicables al tipo de propiedad, para clasificar correctamente cada aviso.**

### Épica C — Participación de la comunidad

**C1. Como usuario registrado, quiero votar si una propiedad tiene o no un criterio, para corregir o validar lo que detectó la IA.**
- Un voto por usuario/criterio/propiedad. Al alcanzar el umbral de coincidencia se aplica el override y se recalcula el score.

**C2. Como usuario registrado, quiero comentar propiedades, para compartir información con otros.**

**C3. Como usuario registrado, quiero guardar propiedades en favoritos, para volver a ellas fácilmente.**

**C4. Como usuario registrado, quiero reportar un aviso, para avisar de información incorrecta o spam.**

### Épica D — Cuentas y personalización

**D1. Como visitante, quiero registrarme, iniciar sesión y recuperar mi contraseña, para acceder a funciones personalizadas.**

**D2. Como usuario registrado, quiero guardar mis preferencias de búsqueda (criterios, zona, operación, precio), para no reconfigurar filtros cada vez.**

### Épica E — Catálogo automatizado

**E1. Como administrador, quiero que los scrapers corran automáticamente una vez al día, para mantener el catálogo actualizado sin intervención.**
- Corrida diaria 03:00 ART de las 3 fuentes. Cada corrida queda en el historial (fuente, inicio, fin, estado, cantidad).
- Deduplicación cross-source. Las propiedades que desaparecen de la fuente se marcan inactivas.

**E2. Como administrador, quiero ejecutar scrapers y el re-análisis manualmente y ver el progreso en vivo, para reaccionar ante incidentes.**
- Progreso por streaming (SSE). El re-análisis no permite dos corridas en paralelo y muestra "Análisis en curso".

### Épica F — Administración y métricas

**F1. Como administrador, quiero un dashboard con totales, distribución de niveles y estado de scrapers, para tener una visión general.**

**F2. Como administrador, quiero ver la evolución histórica de propiedades activas por fuente, para detectar tendencias y caídas anómalas.**
- Snapshot por corrida (fecha, fuente, operación, cantidad). Gráfico de líneas por operación.
- Granularidad **Día / Semana / Mes / Año**. Toggle **Todas / Solo accesibles** (score > 0, igual al contador del header).
- Forward-fill de períodos sin snapshot de una fuente; usa el último snapshot del período (no el promedio); excluye duplicados. Si no hay datos: "Sin datos todavía".

**F3. Como administrador, quiero moderar reportes y comentarios, y activar/desactivar usuarios, para mantener la calidad del contenido.**

**F4. Como administrador, quiero exportar las propiedades a CSV y forzar el re-análisis de una propiedad, para tareas de auditoría y corrección.**
