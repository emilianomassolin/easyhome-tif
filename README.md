# EasyHome — Documentación del Proyecto

## ¿Qué es EasyHome?

Plataforma web que ayuda a personas con movilidad reducida a encontrar viviendas accesibles en Mendoza, Argentina.

El sistema:
1. Obtiene propiedades de **3 fuentes**: MercadoLibre, ZonaProp y MendozaProp
2. Las guarda en PostgreSQL
3. Las analiza con **Claude AI** (texto + imágenes) para detectar accesibilidad
4. Genera un **score del 1 al 10** por propiedad
5. Expone todo mediante una **API REST** con FastAPI

---

## Estado del proyecto

| Sprint | Estado | Descripción |
|---|---|---|
| Sprint 1 — Datos | ✅ Completo | Fetcher ML, scrapers ZonaProp y MendozaProp, BD, API, Scheduler |
| Sprint 2 — IA | ✅ Completo | Análisis NLP + Visión con Claude, score de accesibilidad |
| Sprint 3 — Frontend | ⏳ Pendiente | Interfaz web con filtros |

---

## Cómo probar todo

### 1. Activar entorno e iniciar el servidor

```bash
cd ~/Documentos/easyhome-tif
source .venv/bin/activate
uvicorn backend.main:app --reload
```

### 2. Abrir la documentación interactiva

```
http://localhost:8000/docs
```

Desde ahí podés probar todos los endpoints con botones, sin necesidad de la terminal.

### 3. Probar los endpoints en orden

```bash
# Verificar que el servidor está vivo
curl http://localhost:8000/health

# Ver todas las propiedades (de las 3 fuentes)
curl http://localhost:8000/properties

# Ver detalle de una propiedad
curl http://localhost:8000/properties/1

# Analizar una propiedad con Claude AI (tarda ~3 segundos)
curl -X POST http://localhost:8000/analyze/1

# Analizar todas las propiedades sin analizar de una vez
curl -X POST http://localhost:8000/analyze-all

# Propiedad inexistente → devuelve 404
curl http://localhost:8000/properties/999
```

### 4. Correr los scrapers manualmente

```bash
# Traer propiedades de MendozaProp
python3 -c "from backend.scrapers.mendozaprop_scraper import scrape_mendozaprop; scrape_mendozaprop()"

# Traer propiedades de ZonaProp (usa Playwright, tarda ~15 segundos)
python3 -c "from backend.scrapers.zonaprop_scraper import scrape_zonaprop; scrape_zonaprop()"

# Traer propiedades de MercadoLibre (requiere token configurado)
python3 -c "from backend.ml_integration.fetcher import fetch_properties; fetch_properties()"
```

### 5. Ver el estado de la base de datos

```bash
psql -h localhost -U easyhome_user -d easyhome -c \
  "SELECT fuente, COUNT(*) FROM properties GROUP BY fuente;"
```

---

## ¿Qué se construyó?

### Sprint 1 — Obtención de datos

**Fuente 1: MercadoLibre** (`backend/ml_integration/fetcher.py`)
- Llama a la API oficial de MercadoLibre
- Busca inmuebles en Mendoza con paginación automática
- Usa multiget para obtener descripciones en bulk
- Evita duplicados por `ml_id`
- Maneja rate limit (429) y timeouts con backoff

**Fuente 2: MendozaProp** (`backend/scrapers/mendozaprop_scraper.py`)
- Scraping con `requests` + `BeautifulSoup`
- Parsea los cards de la home de mendozaprop.com
- Extrae: título, precio, ubicación, fotos, permalink

**Fuente 3: ZonaProp** (`backend/scrapers/zonaprop_scraper.py`)
- Scraping con `Playwright` (browser Chromium headless)
- Necesita Playwright porque ZonaProp usa Cloudflare (bloquea requests normales)
- Extrae los datos del objeto `__NEXT_DATA__` de Next.js
- Fallback: parsea el HTML si no encuentra el JSON

**Base de datos** (`backend/database/`)
- PostgreSQL con SQLAlchemy ORM
- Tabla `properties` con campo `fuente` para identificar el origen
- Creación automática de tablas al iniciar el servidor

**Scheduler** (`backend/scheduler/jobs.py`)
- APScheduler ejecuta las 3 fuentes cada 24 horas automáticamente
- Si una fuente falla, las otras siguen funcionando
- Loguea resultados de cada ejecución

**API REST — Sprint 1**
- `GET /health` — estado del servidor
- `GET /properties` — lista todas las propiedades con paginación
- `GET /properties/{id}` — detalle de una propiedad

---

### Sprint 2 — Análisis con IA

**Analizador de texto NLP** (`backend/nlp/analyzer.py`)
- Envía la descripción a Claude AI con un prompt estructurado
- Claude detecta si el texto menciona cada criterio de accesibilidad
- Devuelve JSON con `true/false` por criterio + nivel de confianza

**Analizador de imágenes** (`backend/vision/image_analyzer.py`)
- Descarga las fotos y las envía a Claude AI (modo visión)
- Analiza hasta 5 fotos por propiedad
- Un criterio se considera detectado si aparece en al menos una imagen

**Calculadora de score** (`backend/scoring/calculator.py`)
- Combina NLP y visión con pesos: `60% texto + 40% imágenes`
- Cada criterio detectado suma 1.5 puntos (máximo 10)
- Genera justificación en lenguaje natural
- Asigna nivel: Muy accesible / Accesible / Parcialmente accesible / Poco accesible

**API REST — Sprint 2**
- `POST /analyze/{id}` — analiza una propiedad y guarda el score
- `POST /analyze-all` — analiza todas las pendientes de una vez

---

## Criterios de accesibilidad (7)

| # | Criterio | Detectado por |
|---|---|---|
| 1 | Rampa de acceso | Texto + Imágenes |
| 2 | Ascensor / elevador | Texto + Imágenes |
| 3 | Baño adaptado / barras de apoyo | Texto + Imágenes |
| 4 | Entrada ancha / puerta ancha | Texto + Imágenes |
| 5 | Sin escalones en acceso | Texto + Imágenes |
| 6 | Piso plano / sin desniveles | Texto + Imágenes |
| 7 | Estacionamiento adaptado PMD | Texto + Imágenes |

---

## API REST — Todos los endpoints

| Método | Endpoint | Descripción |
|---|---|---|
| GET | `/health` | Estado del servidor |
| GET | `/properties` | Lista propiedades (paginada, todas las fuentes) |
| GET | `/properties/{id}` | Detalle de una propiedad |
| POST | `/analyze/{id}` | Analiza una propiedad con Claude AI |
| POST | `/analyze-all` | Analiza todas las propiedades sin analizar |

### Ejemplo respuesta GET /properties
```json
{
  "total": 39,
  "propiedades": [
    {
      "id": 4,
      "titulo": "Casa sin escalones - Godoy Cruz",
      "precio": 95000,
      "ubicacion": "Godoy Cruz, Mendoza",
      "permalink_ml": "https://...",
      "score_accesibilidad": 2.7,
      "fecha_creacion": "2026-04-24T13:10:24Z"
    }
  ]
}
```

### Ejemplo respuesta POST /analyze/{id}
```json
{
  "id": 1,
  "titulo": "Depto con rampa y ascensor - Mendoza Centro",
  "score_accesibilidad": 8.5,
  "nivel": "Muy accesible",
  "criterios_detectados": {
    "rampa": true,
    "ascensor": true,
    "bano_adaptado": true,
    "entrada_ancha": false,
    "sin_escalones": true,
    "piso_plano": false,
    "estacionamiento_adaptado": false
  },
  "justificacion": "Rampa de acceso detectada en descripción. Ascensor confirmado. Baño adaptado con barras de apoyo. Sin escalones en acceso. Score final: 8.5/10.",
  "confianza": 0.87
}
```

---

## Stack tecnológico

| Tecnología | Para qué se usa |
|---|---|
| Python 3.12 | Lenguaje base del backend |
| FastAPI + Uvicorn | API REST y servidor web |
| PostgreSQL + SQLAlchemy | Base de datos y ORM |
| APScheduler | Actualización automática cada 24hs |
| Claude API (claude-sonnet-4-5) | Análisis de texto e imágenes con IA |
| Playwright + Chromium | Scraping de ZonaProp (bypasea Cloudflare) |
| BeautifulSoup | Scraping de MendozaProp |
| requests | Llamadas HTTP a MercadoLibre y MendozaProp |
| python-dotenv | Variables de entorno desde `.env` |
| Pytest | Tests de integración |

---

## Estructura de carpetas

```
easyhome-tif/
├── backend/
│   ├── main.py                        # Entry point del servidor
│   ├── api/
│   │   └── routes.py                  # Todos los endpoints REST
│   ├── database/
│   │   ├── models.py                  # Tabla properties (SQLAlchemy)
│   │   └── connection.py              # Conexión a PostgreSQL
│   ├── ml_integration/
│   │   └── fetcher.py                 # Fuente: MercadoLibre
│   ├── scrapers/
│   │   ├── mendozaprop_scraper.py     # Fuente: MendozaProp (BeautifulSoup)
│   │   └── zonaprop_scraper.py        # Fuente: ZonaProp (Playwright)
│   ├── scheduler/
│   │   └── jobs.py                    # APScheduler: corre las 3 fuentes
│   ├── nlp/
│   │   └── analyzer.py                # NLP con Claude API
│   ├── vision/
│   │   └── image_analyzer.py          # Visión con Claude API
│   └── scoring/
│       └── calculator.py              # Score de accesibilidad 1-10
├── tests/
│   └── test_fetcher.py
├── .env
├── requirements.txt
└── README.md
```

---

## Variables de entorno (.env)

```env
DATABASE_URL=postgresql://easyhome_user:1234@localhost/easyhome
ANTHROPIC_API_KEY=sk-ant-...
```

---

## Instalación desde cero

```bash
# 1. Clonar el repositorio
git clone <repo>
cd easyhome-tif

# 2. Crear entorno virtual e instalar dependencias
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
playwright install chromium

# 3. Crear la base de datos en PostgreSQL
sudo -u postgres psql -c "CREATE USER easyhome_user WITH PASSWORD '1234';"
sudo -u postgres psql -c "CREATE DATABASE easyhome OWNER easyhome_user;"
sudo -u postgres psql -d easyhome -c "GRANT ALL ON SCHEMA public TO easyhome_user;"

# 4. Configurar .env con tus credenciales

# 5. Iniciar el servidor
uvicorn backend.main:app --reload
```
