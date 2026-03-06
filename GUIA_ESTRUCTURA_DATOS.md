# Guia de estructura de datos del proyecto

## 1) Alcance del analisis

Se reviso el proyecto completo y el flujo de datos en:

- `app.py`
- `pages/shared.py`
- `core/parser.py`
- `core/catalogos.py`
- carpeta `data/`

Base documental:

- `data/Estructuras Basicas.pdf` (especificacion oficial de layout fijo)

Muestras solicitadas por ti:

- `PPP_MMV_DD_9999.txt`: primeras 10 filas
- `PARTIDOS.txt`: primeras 40 filas
- `DIVIPOL.txt`: primeras 100 filas
- `CANDIDATOS.txt`: primeras 150 filas

## 2) Como esta compuesto el flujo actual de la app

La app carga y transforma datos en este orden:

1. `pages/shared.py::cargar_todo()`
2. `core/parser.py::procesar_mmv()` para `PPP_MMV_DD_9999.txt`
3. `core/catalogos.py` para catalagos (`PARTIDOS`, `CANDIDATOS`, `DIVIPOL`, `CORPORACION`)
4. Las paginas (`pages/*.py`) consumen diccionarios ya agregados

Modelo interno principal (`datos`):

- `datos["mmv"]`: agregados de votacion por candidato, partido, municipio, depto
- `datos["partidos"]`: nombre por codigo de partido
- `datos["candidatos"]`: metadata de candidato por llave `partido_candidato`
- `datos["divipol"]`: nombres geo + potencial y numero de mesas por municipio
- `datos["corporaciones"]`: nombre por codigo de corporacion

## 3) Diccionario de datos por archivo (fixed-width)

Notas:

- Posiciones abajo son 1-based e inclusivas.
- Los archivos vienen con CRLF; al parsear conviene limpiar `\r\n`.

### 3.1 `PPP_MMV_DD_9999.txt` (MMV)

Longitud efectiva del registro: 38 chars (39 en lectura cruda por `\r`).
Volumen actual: 4,693,724 filas.

Campos:

- 1-2: `cod_depto` (2)
- 3-5: `cod_muni` (3)
- 6-7: `zona` (2)
- 8-9: `puesto` (2)
- 10-15: `num_mesa` (6)
- 16-17: `cod_jal` (2)
- 18-21: `num_comunicado` (4, esperado `9999`)
- 22-22: `circunscripcion` (1)
- 23-27: `cod_partido` (5)
- 28-30: `cod_candidato` (3)
- 31-38: `votos` (8)

Codigos especiales de candidato usados por la app:

- `000`: voto de lista (se agrega a partidos)
- `996`: voto en blanco
- `997`: voto nulo
- `998`: no marcado

### 3.2 `PARTIDOS.txt`

Volumen actual: 348 filas.
Longitud observada: 206 chars.

Campos:

- 1-5: `cod_partido` (5)
- 6-205: `nombre_partido` (200)
- 206-206: bandera extra observada (`N`) no usada por la app

### 3.3 `CANDIDATOS.txt`

Volumen actual: 3,676 filas.
Longitud observada: 138 chars.

Campos:

- 1-3: `corporacion` (3)
- 4-4: `circunscripcion` (1)
- 5-6: `cod_depto` (2)
- 7-9: `cod_muni` (3)
- 10-11: `cod_comuna` (2)
- 12-16: `cod_partido` (5)
- 17-19: `cod_candidato` (3)
- 20-20: `preferente` (1)
- 21-70: `nombre` (50)
- 71-120: `apellido` (50)
- 121-135: `cedula` (15)
- 136-136: `genero` (1)
- 137-138: `sorteo` (2)

En la carga actual:

- se excluyen registros con `cod_candidato == "000"` (cabeceras de lista)
- llave de negocio usada: `cand_key = cod_partido + "_" + cod_candidato`

### 3.4 `DIVIPOL.txt`

Volumen actual: 14,394 filas.
Longitud observada: 146 chars.

Campos:

- 1-2: `cod_depto` (2)
- 3-5: `cod_muni` (3)
- 6-7: `cod_zona` (2)
- 8-9: `cod_puesto` (2)
- 10-21: `nombre_depto` (12)
- 22-51: `nombre_municipio` (30)
- 52-91: `nombre_puesto` (40)
- 92-92: `indicador_puesto` (1)
- 93-100: `potencial_hombres` (8)
- 101-108: `potencial_mujeres` (8)
- 109-114: `num_mesas` (6)
- 115-116: `cod_comuna` (2)
- 117-146: `nombre_comuna` (30)

En la carga actual se usan solo:

- depto, muni, nombres, potenciales, num_mesas
- no se usan `zona`, `puesto`, `comuna`, `nombre_puesto`

### 3.5 `INDICADORES.txt`

Volumen actual: 5 filas. Longitud: 105.

- 1-1: `codigo`
- 2-101: `descripcion`
- 102-105: `potencial_max_mesa`

### 3.6 `CIRCUNSCRIPCION.txt`

Volumen actual: 5 filas. Longitud: 101.

- 1-1: `codigo_circ`
- 2-101: `descripcion`

Valores observados: `0,1,4,5,9`.

### 3.7 `CORPORACION.txt`

Volumen actual: 4 filas. Longitud: 203.

- 1-3: `cod_corporacion`
- 4-203: `nombre_corporacion`

## 4) Relacionamiento entre archivos (llaves)

Relaciones principales:

1. MMV -> PARTIDOS

- `PPP_MMV.cod_partido` = `PARTIDOS.cod_partido`

1. MMV -> CANDIDATOS

- `PPP_MMV.cod_partido + "_" + PPP_MMV.cod_candidato`
- `= CANDIDATOS.cod_partido + "_" + CANDIDATOS.cod_candidato`
- aplica para candidatos reales (`!= 000/996/997/998`)

1. MMV -> DIVIPOL (nivel municipio)

- `PPP_MMV.cod_depto + "_" + PPP_MMV.cod_muni`
- `= DIVIPOL.cod_depto + "_" + DIVIPOL.cod_muni`

1. MMV -> DIVIPOL (nivel puesto)

- `PPP_MMV.cod_depto + "_" + cod_muni + "_" + zona + "_" + puesto`
- `= DIVIPOL.cod_depto + "_" + cod_muni + "_" + cod_zona + "_" + cod_puesto`

1. CANDIDATOS -> CORPORACION

- `CANDIDATOS.corporacion = CORPORACION.cod_corporacion`

1. MMV/CANDIDATOS -> CIRCUNSCRIPCION

- `circunscripcion` contra catalogo `CIRCUNSCRIPCION`

## 5) Cardinalidades y cobertura observadas

MMV:

- filas: 4,693,724
- deptos: 34
- municipios: 1,189
- mesas unicas: 125,161
- partidos en MMV: 211
- combinaciones `partido_candidato`: 1,078
- circunscripciones presentes en MMV: `1,4,5`

Conteo de codigos candidato MMV:

- `000` lista: 1,247,301
- `996` blanco: 220,475
- `997` nulo: 220,782
- `998` no marcado: 220,564
- reales: 2,784,602

CANDIDATOS:

- filas: 3,676
- cabeceras (`000`): 524
- candidatos reales: 3,152
- candidatos reales unicos (`partido_candidato`): 2,506

DIVIPOL:

- filas: 14,394
- municipios: 1,189
- puestos: 14,394
- mesas totales declaradas: 125,259

Cobertura de joins:

- partidos MMV sin catalogo PARTIDOS: 1 (`00000`, usado para especiales)
- candidatos MMV reales sin catalogo CANDIDATOS: 0
- municipios MMV sin DIVIPOL: 0
- puestos MMV sin DIVIPOL: 0
- puestos DIVIPOL sin MMV: 7 (sin votos reportados en el corte actual)

## 6) Lo que hoy usa y no usa la app (importante para refinamiento)

`core/parser.py` (MMV):

- SI usa: depto, muni, zona, puesto, mesa, circ, partido, candidato, votos
- NO usa: `num_comunicado`, `cod_jal`

`core/catalogos.py`:

- PARTIDOS: ignora columna 206 (bandera final)
- CANDIDATOS: ignora `circunscripcion`, `cod_depto`, `cod_muni`, `cod_comuna`, `sorteo`
- DIVIPOL: agrega por municipio e ignora detalle de puesto/comuna en estructura final

Implicacion:

- El dashboard esta optimizado para agregados rapidos en memoria, pero pierde
  granularidad util para auditoria (comuna, puesto nominal, jal, comunicado).

## 7) Recomendaciones directas para la siguiente fase

1. Crear un modulo `core/schema.py` con offsets centralizados por archivo
   para evitar desalineaciones silenciosas.
2. Incorporar validaciones de calidad al cargar:
   - longitudes esperadas
   - codigos de circunscripcion/corporacion validos
   - llaves foraneas faltantes
3. Conservar metadatos hoy descartados:
   - MMV: `num_comunicado`, `cod_jal`
   - CANDIDATOS: geografia, circunscripcion, sorteo
   - DIVIPOL: zona/puesto/comuna/nombre_puesto
4. Agregar una capa de "dimensiones" y "hechos":
   - hechos: MMV
   - dimensiones: partido, candidato, corporacion, circunscripcion, geografia
5. Generar pruebas unitarias de parsing con lineas fijas de ejemplo
   (incluyendo tildes latin-1 y casos especiales `000/996/997/998`).
