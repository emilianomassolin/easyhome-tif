# EasyHome — Documento de exposición

> Plataforma web que centraliza avisos inmobiliarios de Mendoza y los clasifica
> automáticamente según su **nivel de accesibilidad para personas con movilidad
> reducida**, usando inteligencia artificial para analizar texto e imágenes.

Este documento sirve como guion de exposición: explica el problema, la solución,
la arquitectura, las tecnologías y las decisiones técnicas más interesantes.

---

## 1. El problema

Buscar una vivienda accesible en Argentina es hoy prácticamente imposible desde
los portales tradicionales (ZonaProp, MercadoLibre, etc.). Ninguno permite filtrar
por características de accesibilidad: rampa, ascensor, baño adaptado, planta baja,
ducha a nivel de piso, pasamanos, etc.

Una persona en silla de ruedas, un adulto mayor o alguien en rehabilitación tiene
que abrir aviso por aviso, leer la descripción completa y mirar cada foto para
adivinar si la propiedad es apta. Es un trabajo manual, lento y frustrante — y en
muchos casos la información ni siquiera está escrita: hay que deducirla de las fotos.

**EasyHome resuelve exactamente eso.**

---

## 2. La solución en una frase

EasyHome **recolecta** avisos de varias fuentes, los **deduplica**, los **analiza
con IA** (texto + imágenes), les asigna un **score de accesibilidad de 0 a 10**, y
los publica en un buscador donde se puede **filtrar por accesibilidad**, con
participación de la comunidad para corregir y validar.

Flujo conceptual:

```
Portales inmobiliarios
      │  scraping automático diario
      ▼
  Deduplicación (misma propiedad en varias fuentes → una sola)
      │
      ▼
  Análisis de accesibilidad con IA
      │   - NLP sobre la descripción (texto)
      │   - Visión sobre las fotos (imágenes)
      ▼
  Score 0-10 + nivel (Poco / Parcialmente / Accesible / Muy accesible)
      │
      ▼
  Buscador web con filtros por accesibilidad + votación comunitaria
```

---

## 3. Arquitectura general

### 3.1 Diagrama de componentes

```
                          ┌──────────────────────────┐
       Usuario  ───────►  │   Vercel (frontend SPA)   │
                          │   React 19 + Vite + TW     │
                          └────────────┬──────────────┘
                                       │  reverse proxy: /api/* → tunnel
                                       ▼
                          ┌──────────────────────────┐
                          │   Cloudflare Tunnel        │  URL pública
                          │   (*.trycloudflare.com)    │  auto-actualizada al reiniciar
                          └────────────┬──────────────┘
                                       ▼
   ┌───────────────────────────────────────────────────────────────────┐
   │                     VM (OpenStack) · systemd                        │
   │                                                                     │
   │   ┌─────────────────────────┐      ┌───────────────────────────┐   │
   │   │  Uvicorn / FastAPI       │◄────►│  APScheduler (in-process)  │   │
   │   │  - API pública (/api)    │      │  CronTrigger 03:00 ART     │   │
   │   │  - API admin (/api/admin)│      │  → scraping + análisis     │   │
   │   │  - Auth (JWT)            │      │    diario automático       │   │
   │   │  - sirve el frontend     │      └───────────────────────────┘   │
   │   └────────┬─────────────────┘                                      │
   │            │                                                        │
   │   ┌────────▼─────────┐   ┌──────────────┐   ┌──────────────────┐    │
   │   │  PostgreSQL      │   │ FlareSolverr │   │  Scrapers        │    │
   │   │  + pg_trgm       │   │ (Docker)     │◄──┤  ZP / MP / AP    │    │
   │   └──────────────────┘   │ bypass CF    │   └──────────────────┘    │
   │                          └──────────────┘                          │
   └───────────────────────────────────────────────────────────────────┘
                                       │
              ┌────────────────────────┴────────────────────────┐
              ▼                                                  ▼
   ┌────────────────────────┐                      ┌──────────────────────────┐
   │  API NLP (universidad) │                      │  Anthropic API (Claude)  │
   │  gemma4-26b            │                      │  claude-sonnet-4-6       │
   │  texto + score de fotos│                      │  (visión de imágenes)    │
   └────────────────────────┘                      └──────────────────────────┘
```

### 3.2 Por qué esta arquitectura

- **Separación frontend / backend**: el frontend (SPA React) se sirve desde Vercel
  (CDN global, rápido); el backend (FastAPI) corre en una VM con acceso a la base
  de datos, los scrapers y las APIs de IA.
- **Cloudflare Tunnel** expone la VM a internet sin abrir puertos ni IP pública. Un
  detalle interesante: al ser un *quick tunnel*, la URL cambia en cada reinicio, así
  que se implementó un servicio de systemd que detecta la nueva URL al bootear y
  actualiza automáticamente la configuración del proxy en Vercel vía la API de GitHub.
- **Vercel como reverse proxy**: todas las llamadas `/api/*` del frontend se
  redirigen al tunnel, de modo que el usuario nunca ve la URL cambiante.

---

## 4. Stack tecnológico

| Capa | Tecnología | Rol |
|------|-----------|-----|
| **Frontend** | React 19, Vite 8, Tailwind CSS 4 | SPA. Streaming en vivo (SSE) del progreso de scrapers/análisis. Gráficos SVG propios. |
| **Backend** | Python, FastAPI, Uvicorn, Pydantic | API REST + sirve el frontend. |
| **Base de datos** | PostgreSQL, SQLAlchemy 2.0 | ORM. Extensión `pg_trgm` para similitud difusa de texto. JSONB para resultados de IA. |
| **Scraping** | BeautifulSoup4, requests, FlareSolverr, curl_cffi | FlareSolverr (Docker) para bypass anti-bot de Cloudflare; curl_cffi como alternativa rápida por impersonación de TLS. |
| **IA — texto** | API de la universidad (`gemma4-26b`) | Detecta criterios de accesibilidad en la descripción. |
| **IA — visión** | Anthropic Claude (`claude-sonnet-4-6`) | Detecta criterios visuales en las fotos. |
| **Autenticación** | JWT (python-jose), bcrypt (passlib) | Registro, login, recuperación de contraseña. |
| **Tareas programadas** | APScheduler | Scraping + análisis diario automático. |
| **Infraestructura** | OpenStack VM, systemd, Cloudflare Tunnel, Vercel, ZeroTier | Despliegue y acceso remoto. |
| **Calidad** | pytest (102 tests), ESLint | Testing backend + linting frontend. |

---

## 5. El corazón del sistema: análisis de accesibilidad

Este es el componente más novedoso y el que da valor al proyecto. Funciona como un
**pipeline en cascada**, diseñado para maximizar precisión y minimizar costo de IA.

```
1. PRE-FILTRO de palabras clave
   ¿La descripción menciona alguna palabra de accesibilidad
   (rampa, ascensor, baño adaptado, movilidad reducida, ...)?
   │  NO  → resultado vacío, NO se gasta ni un token de IA
   ▼  SÍ
2. NLP sobre el TEXTO
   Un modelo de lenguaje analiza la descripción y devuelve, en JSON,
   qué criterios de accesibilidad detecta.
   │  Sin criterios → no se manda a visión
   ▼  Con criterios
3. VISIÓN sobre las IMÁGENES (solo si el texto dio positivo)
   - Un modelo puntúa cada foto por relevancia (¿muestra entrada, baño,
     escalera?) y se quedan las 3 mejores.
   - Esas 3 fotos van a Claude, que detecta criterios visuales.
   ▼
4. SCORING
   Se combinan texto + visión (+ correcciones de la comunidad) en un
   score de 0 a 10 y un nivel textual.
```

### 5.1 Los 8 criterios de accesibilidad

Rampa · Ascensor · Baño adaptado · Entrada ancha · Estacionamiento adaptado (PMD) ·
Ducha a nivel de piso · Pasamanos · Planta baja.

### 5.2 Cálculo del score

El score es un **promedio simple**: `(criterios detectados / criterios aplicables) × 10`.
Cada criterio pesa lo mismo.

Un detalle inteligente: **los criterios aplicables dependen del tipo de propiedad**.
Un terreno o una cochera no necesitan ascensor ni baño adaptado, así que esos
criterios se excluyen del denominador — de lo contrario un terreno nunca podría ser
"accesible".

Niveles según el score:

| Nivel | Score |
|-------|-------|
| Muy accesible | ≥ 8.5 |
| Accesible | 6 – 8.4 |
| Parcialmente accesible | 3.5 – 5.9 |
| Poco accesible | < 3.5 |

### 5.3 Por qué la cascada (decisión de diseño para exponer)

El análisis con IA cuesta dinero y tiempo. El pre-filtro de keywords descarta gratis
la enorme mayoría de avisos (los que ni mencionan accesibilidad), y la visión solo
se ejecuta cuando el texto ya dio señales. Resultado: se analiza a fondo solo lo que
vale la pena, ahorrando ~80% de las llamadas costosas de IA.

---

## 6. Deduplicación cross-source (decisión técnica destacada)

La misma propiedad suele estar publicada en ZonaProp **y** en MendozaProp. Mostrarla
dos veces sería una mala experiencia. Para detectarlo se usa la extensión `pg_trgm`
de PostgreSQL (similitud por trigramas de texto):

- Se comparan las **direcciones** con `similarity()`.
- Umbral base: similitud ≥ 0.80.
- Se **baja el umbral a 0.65** si además coinciden la **superficie en m²** (±15%) y/o
  la **cantidad de ambientes** (extraídos de la descripción con regex).
- Si se encuentra un duplicado, se marca con una columna `duplicate_of` que apunta a
  la propiedad "canónica". La API pública siempre filtra `duplicate_of IS NULL`.

Esto elimina ~500 duplicados del catálogo y hace que los conteos sean honestos.

---

## 7. Modelo de datos

Tablas principales (PostgreSQL vía SQLAlchemy):

- **`properties`** — el núcleo. Datos del aviso (título, precio, descripción,
  ubicación, fotos) + resultados de IA (`nlp_resultado`, `vision_resultado`,
  `score_accesibilidad`, `justificacion`) + `manual_override` (correcciones de la
  comunidad) + `duplicate_of`, `superficie_m2`, `ambientes`.
- **`users`, `user_preferences`, `favorites`** — cuentas, preferencias de búsqueda,
  favoritos.
- **`comentarios`, `votos_criterios`** — participación comunitaria (comentarios y
  votos sí/no por criterio).
- **`reports`** — reportes de usuarios para moderación.
- **`scraper_logs`** — historial de cada corrida de scraper (manual y automática).
- **`snapshots_propiedades`** — métrica histórica para el gráfico de evolución del
  catálogo en el tiempo (timeline).

---

## 8. Frontend y experiencia de usuario

- **Buscador** con filtros por operación (venta/alquiler), tipo, zona (departamentos
  de Mendoza), fuente, score mínimo y criterios específicos. Orden por score.
- **Detalle de propiedad**: score, nivel, justificación legible, criterios detectados
  (por texto, imagen o votos de la comunidad), galería de fotos, comentarios y
  votación de criterios.
- **Cuentas de usuario**: registro/login, favoritos, preferencias, reportes.
- **Panel de administración** (7 pestañas): Dashboard con métricas, gestión de
  Propiedades, moderación de Reportes, control de Scrapers, Análisis masivo,
  Usuarios, y Timeline de evolución del catálogo.
- **Tiempo real**: el panel muestra el progreso de scrapers y análisis en vivo
  mediante Server-Sent Events (SSE), con reconexión automática y bloqueo de corridas
  concurrentes.

---

## 9. Automatización y despliegue

- **Scraping diario automático**: un `CronTrigger` de APScheduler dispara todas las
  noches a las 03:00 ART el scraping de las 3 fuentes + análisis + snapshot de
  métricas. Cada corrida queda registrada.
- **Despliegue**: `deploy.sh` sincroniza el backend a la VM, construye y copia el
  frontend, reinicia el servicio con systemd y hace push a GitHub (que dispara el
  redeploy del frontend en Vercel).
- **Resiliencia**: servicios systemd con `Restart=always`; el tunnel se auto-actualiza
  en Vercel al reiniciar; los scrapers registran su estado; el análisis, ante fallos
  de la API de IA, deja las propiedades pendientes para reintentar (no genera falsos
  negativos).

---

## 10. Retos técnicos interesantes (buenos para exponer)

Estos son los problemas reales que surgieron y cómo se resolvieron — son los puntos
que más lucen en una defensa porque muestran criterio de ingeniería.

### 10.1 Bypass de Cloudflare y la evolución del scraping
ZonaProp está protegido por el anti-bot de Cloudflare. Se resolvió con **FlareSolverr**
(un navegador headless que resuelve el desafío JS). Más tarde, para acelerar un
backfill masivo de descripciones, se descubrió que **`curl_cffi`** (que impersona el
fingerprint TLS de un Chrome real) podía pasar Cloudflare **sin navegador**, ~20 veces
más rápido y sin consumir CPU. Lección: a veces la solución rápida no es más hardware,
sino una técnica distinta.

### 10.2 Dependencia de una API externa inestable
El análisis de texto usa un modelo de IA alojado por la universidad. Durante el
desarrollo, ese servicio **eliminó el modelo configurado** (`gemma4-e2b`) y luego tuvo
**caídas intermitentes** de disponibilidad. Se resolvió: (a) migrando al modelo
sucesor (`gemma4-26b`); (b) haciendo el análisis **tolerante a fallos** (ante un
timeout, la propiedad queda pendiente en vez de marcarse mal); y (c) preparando
**Claude (Anthropic) como respaldo** para re-análisis masivos cuando la API de la
universidad no está disponible. Lección: diseñar para que las fallas externas
degraden con gracia, no corrompan datos.

### 10.3 Inestabilidad de la URL del túnel
El *quick tunnel* de Cloudflare cambia de URL en cada reinicio, lo que dejaba el sitio
sin datos. Se automatizó con un servicio de systemd que, al bootear, extrae la nueva
URL y actualiza el reverse proxy de Vercel vía la API de GitHub. Lección: automatizar
lo que se rompe repetidamente.

### 10.4 Consistencia de métricas
El panel de admin y la página pública contaban distinto (uno incluía duplicados, el
otro no). Se unificó todo bajo el mismo criterio (`activa AND duplicate_of IS NULL`).
Lección: una sola fuente de verdad para los conteos.

---

## 11. Resultados

- Catálogo de **~27.400 propiedades activas** de 3 fuentes, deduplicadas.
- **~6.900 propiedades con accesibilidad detectada**, clasificadas por nivel.
- Análisis de accesibilidad de **texto + imágenes** con IA, algo que ningún portal
  tradicional ofrece.
- Participación comunitaria para corregir la IA (votación de criterios).
- Pipeline **totalmente automatizado**: scraping, deduplicación, análisis y métricas
  corren solos todas las noches.

---

## 12. Posibles trabajos futuros

- **Modelo propio de visión** entrenado con datos etiquetados por la comunidad
  (idea: interfaz tipo "captcha" donde el usuario marca en qué parte de la foto se ve
  cada característica de accesibilidad).
- **Ponderación de criterios** (que un baño adaptado pese más que planta baja).
- **Alertas** por email cuando aparece una propiedad accesible que cumple las
  preferencias del usuario.
- **Más fuentes** y expansión a otras provincias.
- **Robustez de la IA**: independizarse de la API de la universidad usando un modelo
  propio o un proveedor confiable.

---

## Apéndice — Guion breve para la exposición oral

1. **Problema** (30 s): "Ningún portal deja filtrar viviendas por accesibilidad;
   hoy hay que revisar aviso por aviso a mano."
2. **Solución** (30 s): "EasyHome recolecta, deduplica y clasifica automáticamente
   los avisos por accesibilidad usando IA sobre texto e imágenes."
3. **Arquitectura** (1 min): mostrar el diagrama — SPA en Vercel, backend FastAPI en
   una VM, PostgreSQL, scrapers, y dos motores de IA (texto y visión).
4. **El pipeline de IA** (1 min): explicar la cascada keyword → texto → visión →
   score, y por qué ahorra costo.
5. **Deduplicación** (30 s): pg_trgm + superficie/ambientes → una sola propiedad.
6. **Un reto real** (1 min): elegir uno de la sección 10 (el de Cloudflare/curl_cffi o
   el de la API inestable lucen muy bien).
7. **Resultados y futuro** (30 s): números del catálogo + trabajos futuros.
