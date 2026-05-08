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
# Traer propiedades de MendozaProp (usa API interna, rápido)
python3 -c "from backend.scrapers.mendozaprop_scraper import scrape_mendozaprop; scrape_mendozaprop()"

# Traer propiedades de ZonaProp (usa Playwright, tarda ~15 minutos por volumen)
python3 -c "from backend.scrapers.zonaprop_scraper import scrape_zonaprop; scrape_zonaprop()"

# Traer propiedades de MercadoLibre (requiere OAuth configurado)
python3 -c "from backend.ml_integration.fetcher import fetch_properties; fetch_properties()"

# Configurar OAuth de MercadoLibre (una sola vez)
python -m backend.ml_integration.ml_oauth_setup
```

### 5. Ver el estado de la base de datos

```bash
psql -h localhost -U easyhome_user -d easyhome -c \
  "SELECT fuente, COUNT(*) as total, SUM(CASE WHEN activa THEN 1 ELSE 0 END) as activas FROM properties GROUP BY fuente;"
```

---

## ¿Qué se construyó?

### Sprint 1 — Obtención de datos

**Fuente 1: MercadoLibre** (`backend/ml_integration/fetcher.py`)
- Llama a la API oficial de MercadoLibre con OAuth 2.0 (Authorization Code flow)
- Busca inmuebles en Mendoza con paginación automática
- Usa multiget para obtener descripciones en bulk
- Evita duplicados por `ml_id`
- Maneja rate limit (429) y timeouts con backoff
- Token de acceso se renueva automáticamente con refresh token

**Fuente 2: MendozaProp** (`backend/scrapers/mendozaprop_scraper.py`)
- Detectada API REST interna del sitio: `mendozaprop.com/api/properties`
- Paginación por offset (PAGE_SIZE=50), sin necesidad de navegador
- Trae venta y alquiler por separado (operationType 1 y 2)
- Extrae: título, precio, descripción completa, ubicación, todas las fotos, habitaciones, baños, m², cocheras
- Implementa mark-and-sweep para detectar propiedades dadas de baja

**Fuente 3: ZonaProp** (`backend/scrapers/zonaprop_scraper.py`)
- Scraping con `Playwright` (browser Chromium headless)
- Requiere Playwright porque ZonaProp usa Cloudflare Turnstile como protección anti-bot
- No tiene API interna accesible: los datos están en el HTML renderizado
- Crea un contexto de browser nuevo por página para evitar bloqueos
- Implementa mark-and-sweep para detectar propiedades dadas de baja

**Base de datos** (`backend/database/`)
- PostgreSQL con SQLAlchemy ORM
- Tabla `properties` con campo `fuente` para identificar el origen
- Campo `activa` para saber si la propiedad sigue publicada
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

## Estrategia de actualización de propiedades (Mark and Sweep)

Cada vez que se corre un scraper, el sistema sigue este proceso:

1. **Mark**: todas las propiedades existentes de esa fuente se marcan como `activa = False`
2. **Sweep**: por cada propiedad encontrada en el scrape:
   - Si ya existe en la BD → se marca `activa = True` y se actualizan precio, fotos y descripción si cambiaron
   - Si no existe → se crea como `activa = True`
3. Las propiedades que no aparecieron quedan con `activa = False`, lo que indica que fueron dadas de baja en el sitio (vendidas, alquiladas o retiradas)

Esto permite saber en tiempo real qué propiedades siguen disponibles sin borrar el historial.

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
| requests | Llamadas HTTP a MercadoLibre y MendozaProp API |
| python-dotenv | Variables de entorno desde `.env` |
| Pytest | Tests de integración |

---

## Estructura de carpetas

```
easyhome-tif/
├── backend/
│   ├── main.py                            # Entry point del servidor
│   ├── api/
│   │   └── routes.py                      # Todos los endpoints REST
│   ├── database/
│   │   ├── models.py                      # Tabla properties (SQLAlchemy)
│   │   └── connection.py                  # Conexión a PostgreSQL
│   ├── ml_integration/
│   │   ├── fetcher.py                     # Fuente: MercadoLibre API
│   │   ├── auth.py                        # OAuth 2.0 con refresh token
│   │   └── ml_oauth_setup.py              # Setup inicial del token OAuth
│   ├── scrapers/
│   │   ├── mendozaprop_scraper.py         # Fuente: MendozaProp (API interna)
│   │   └── zonaprop_scraper.py            # Fuente: ZonaProp (Playwright)
│   ├── scheduler/
│   │   └── jobs.py                        # APScheduler: corre las 3 fuentes
│   ├── nlp/
│   │   └── analyzer.py                    # NLP con Claude API
│   ├── vision/
│   │   └── image_analyzer.py              # Visión con Claude API
│   └── scoring/
│       └── calculator.py                  # Score de accesibilidad 1-10
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
ML_APP_ID=...
ML_CLIENT_SECRET=...
ML_ACCESS_TOKEN=...
ML_REFRESH_TOKEN=...
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

# 5. Configurar OAuth de MercadoLibre (una sola vez)
python -m backend.ml_integration.ml_oauth_setup

# 6. Iniciar el servidor
uvicorn backend.main:app --reload
```

---

## Prompt para generar Historias de Usuario con Claude

Copiá y pegá este prompt en [claude.ai](https://claude.ai) para generar las historias de usuario del proyecto:

```
Sos un analista funcional experto en metodologías ágiles. Necesito que generes las historias de usuario para un sistema llamado EasyHome.

## Contexto del proyecto

EasyHome es una plataforma web que ayuda a personas con movilidad reducida a encontrar viviendas accesibles en Mendoza, Argentina. El sistema:
- Obtiene propiedades de 3 fuentes: MercadoLibre, ZonaProp y MendozaProp
- Analiza cada propiedad con IA (Claude AI) para detectar características de accesibilidad en texto e imágenes
- Genera un score de accesibilidad del 1 al 10
- Expone los resultados mediante una API REST y un frontend web con filtros

## Criterios de accesibilidad que detecta el sistema
1. Rampa de acceso
2. Ascensor / elevador
3. Baño adaptado / barras de apoyo
4. Entrada ancha / puerta ancha
5. Sin escalones en acceso
6. Piso plano / sin desniveles
7. Estacionamiento adaptado para personas con discapacidad

## Usuarios del sistema
- Persona con movilidad reducida buscando vivienda
- Familiar o cuidador buscando vivienda para un tercero
- Administrador del sistema

## Sprints del proyecto
- Sprint 1: Obtención y almacenamiento de datos (scrapers + API básica)
- Sprint 2: Análisis con IA y score de accesibilidad
- Sprint 3: Frontend web con filtros y búsqueda

## Lo que necesito

Generá historias de usuario para los 3 sprints usando el formato estándar:

**Como** [tipo de usuario], **quiero** [acción o funcionalidad], **para** [beneficio o resultado esperado].

Cada historia debe incluir:
- Título corto
- Historia en formato estándar
- Criterios de aceptación (3 a 5 puntos, en formato de lista de verificación)
- Prioridad: Alta / Media / Baja
- Sprint al que pertenece

Generá al menos 15 historias de usuario en total, distribuidas entre los 3 sprints. Ordená por prioridad dentro de cada sprint.
```
