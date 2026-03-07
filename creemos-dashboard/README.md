# PROMPT — App Angular E-14 CREEMOS (Testigos Electorales)

## CONTEXTO DEL PROYECTO

Aplicación Angular para que testigos electorales del partido CREEMOS reporten los
resultados del formulario E-14 (conteo de votos por mesa) en tiempo real durante
las elecciones al Congreso de Colombia.

El sistema recibe los datos del testigo, los transforma al formato oficial de 38
caracteres del archivo MMV de la Registraduría, y los sube a Firestore. Una app
Streamlit independiente lee esos registros desde Firestore para mostrar resultados
en tiempo real.

Ya existe un proyecto Angular con template PrimeNG. Solo debes crear
los componentes nuevos, registrarlos en el router y agregar los items al sidebar.
No modifiques la estructura base del proyecto ni los archivos de configuración
existentes.

---

## ASSETS DISPONIBLES (ya generados, en `src/assets/data/`)

### `divipol_antioquia.json`
```json
{
  "depto": { "cod": "01", "nombre": "ANTIOQUIA" },
  "municipios": [
    {
      "cod": "001",
      "nombre": "MEDELLIN",
      "puestos": [
        {
          "zona": "01",
          "cod_puesto": "01",
          "nombre": "SEC. ESC. LA ESPERANZA No 2",
          "num_mesas": 39
        }
      ]
    }
  ]
}
```
125 municipios, 1.125 puestos de votación, 15.519 mesas totales en Antioquia.

### `candidatos_creemos.json`
```json
{
  "partido": {
    "cod_senado": "01070",
    "cod_camara": "01067",
    "nombre": "CREEMOS"
  },
  "senado": {
    "corporacion": "001",
    "circunscripcion": "0",
    "circunscripcion_nombre": "NACIONAL",
    "candidatos": [
      { "cod_candidato": "000", "nombre_completo": "CREEMOS", "es_lista": true },
      { "cod_candidato": "001", "nombre_completo": "JULIANA GUTIERREZ ZULUAGA", "es_lista": false },
      { "cod_candidato": "002", "nombre_completo": "ANDRES FELIPE BEDOYA RENDON", "es_lista": false }
    ]
  },
  "camara_antioquia": {
    "corporacion": "002",
    "circunscripcion": "1",
    "circunscripcion_nombre": "TERRITORIAL DEPARTAMENTAL",
    "cod_depto": "01",
    "candidatos": [
      { "cod_candidato": "000", "nombre_completo": "CREEMOS", "es_lista": true },
      { "cod_candidato": "101", "nombre_completo": "LUIS GUILLERMO PATIÑO ARISTIZABAL", "es_lista": false },
      { "cod_candidato": "117", "nombre_completo": "GERMAN DARIO HOYOS GIRALDO", "es_lista": false }
    ]
  }
}
```
22 candidatos Senado + 18 candidatos Cámara (incluyendo cabecera de lista cod=000).

---

## FORMATO MMV — REGISTRO DE 38 CARACTERES

Cada voto reportado genera una línea de exactamente 38 caracteres:

```
Posición  Longitud  Campo             Ejemplo
[0:2]     2         cod_depto         "01"         (siempre Antioquia)
[2:5]     3         cod_muni          "001"         (del municipio seleccionado)
[5:7]     2         zona              "01"          (del puesto seleccionado en DIVIPOL)
[7:9]     2         cod_puesto        "01"          (del puesto seleccionado en DIVIPOL)
[9:15]    6         num_mesa          "000001"      (número de mesa, zero-padded)
[15:17]   2         cod_jal           "00"          (siempre "00")
[17:21]   4         campo_fijo        "9999"        (siempre "9999")
[21:22]   1         circunscripcion   "0"           (0=Senado, 1=Cámara)
[22:27]   5         cod_partido       "01070"       (Senado) o "01067" (Cámara)
[27:30]   3         cod_candidato     "001"         (del candidato, "000" para lista)
[30:38]   8         votos             "00000045"    (votos, zero-padded a 8 dígitos)
```

**Función de construcción del registro (TypeScript):**
```typescript
function buildMMVRecord(
  codMuni: string,      // "001"
  zona: string,         // "01"
  codPuesto: string,    // "01"
  numMesa: number,      // 1
  circunscripcion: string, // "0" o "1"
  codPartido: string,   // "01070" o "01067"
  codCandidato: string, // "001", "002", ... o "000" para lista
  votos: number
): string {
  const pad = (s: string | number, len: number, char = '0') =>
    String(s).padStart(len, char);

  return (
    '01' +                        // cod_depto (siempre Antioquia)
    pad(codMuni, 3) +             // cod_muni
    pad(zona, 2) +                // zona
    pad(codPuesto, 2) +           // cod_puesto
    pad(numMesa, 6) +             // num_mesa
    '00' +                        // cod_jal
    '9999' +                      // campo_fijo
    circunscripcion +             // circunscripcion
    pad(codPartido, 5) +          // cod_partido
    pad(codCandidato, 3) +        // cod_candidato
    pad(votos, 8)                 // votos
  );
  // Resultado debe tener exactamente 38 caracteres - validar siempre
}
```

---

## ESTRUCTURA FIRESTORE

### Colección: `mesas_reportadas`
Documento por cada mesa enviada. El ID del documento es la `mesa_key`.

```typescript
interface MesaReportada {
  mesa_key: string;          // "01_001_01_01_000001" (depto_muni_zona_puesto_mesa)
  cod_depto: string;         // "01"
  cod_muni: string;          // "001"
  nom_muni: string;          // "MEDELLIN"
  zona: string;              // "01"
  cod_puesto: string;        // "01"
  nom_puesto: string;        // "SEC. ESC. LA ESPERANZA No 2"
  num_mesa: number;          // 1
  corporacion: string;       // "001" (Senado) | "002" (Cámara)
  corporacion_nombre: string;// "SENADO" | "CAMARA"
  circunscripcion: string;   // "0" | "1"
  cod_partido: string;       // "01070" | "01067"
  registros_mmv: string[];   // Array de strings de 38 chars
  total_votos: number;       // Suma de todos los votos reportados
  testigo_uid: string;       // UID del usuario autenticado
  testigo_email: string;
  timestamp: Timestamp;
  estado: 'enviado';
}
```

### Colección: `resumen_municipios` (actualizada por Cloud Function o desde Angular)
```typescript
interface ResumenMunicipio {
  cod_muni: string;
  nom_muni: string;
  total_puestos: number;
  puestos_reportados: number;
  total_mesas: number;
  mesas_reportadas: number;
  porcentaje_avance: number;
}
```

---

## MÓDULOS Y COMPONENTES A CREAR

### 1. `CatalogoService` — `src/app/services/catalogo.service.ts`

Servicio singleton que carga los JSON de assets una sola vez al iniciar la app
y los expone como observables/signals. Nunca vuelve a leerlos.

```typescript
// Métodos que debe exponer:
getMunicipios(): Municipio[]
getPuestosByMunicipio(codMuni: string): Puesto[]
getMesasByPuesto(codMuni: string, zona: string, codPuesto: string): number[]
getCandidatosByCorporacion(corporacion: 'senado' | 'camara'): Candidato[]
getPartidoCod(corporacion: 'senado' | 'camara'): string
getCircunscripcion(corporacion: 'senado' | 'camara'): string
```

### 2. `FirestoreService` — `src/app/services/firestore.service.ts`

Servicio que encapsula toda la lógica de Firestore:
- `submitMesa(data: MesaReportada): Promise<void>`
- `getMesasReportadas(): Observable<MesaReportada[]>` (tiempo real con onSnapshot)
- `getMesasByMunicipio(codMuni: string): Observable<MesaReportada[]>`
- `checkMesaExiste(mesaKey: string): Promise<boolean>`

### 3. `MmvBuilderService` — `src/app/services/mmv-builder.service.ts`

Servicio puro (sin estado) con la lógica de construcción del formato MMV:
- `buildRecords(formData: E14FormData): string[]` — retorna array de strings de 38 chars
- `validateRecord(record: string): boolean` — valida longitud y formato
- `buildMesaKey(codMuni, zona, codPuesto, numMesa): string`

### 4. `E14FormComponent` — `src/app/e14/e14-form/e14-form.component`

**Formulario principal de ingreso del E-14.**

**Campos (en orden, con dependencias encadenadas):**

1. **Corporación** — `p-selectButton` con dos opciones:
   - `SENADO` (valor: `'senado'`)
   - `CÁMARA` (valor: `'camara'`)
   - Al cambiar: limpia todos los campos siguientes y recarga candidatos

2. **Municipio** — `p-dropdown` con búsqueda
   - Opciones: todos los municipios de Antioquia del JSON
   - Mostrar: nombre del municipio
   - Al cambiar: limpia puesto y mesa

3. **Puesto de Votación** — `p-dropdown` con búsqueda
   - Opciones: puestos del municipio seleccionado
   - Mostrar: nombre del puesto
   - Oculto/deshabilitado hasta que se seleccione municipio
   - Al cambiar: limpia mesa
   - **La zona se obtiene automáticamente del puesto seleccionado — no se muestra al usuario**

4. **Mesa** — `p-dropdown`
   - Opciones: números del 1 al `num_mesas` del puesto seleccionado
   - Mostrar: "Mesa 1", "Mesa 2", etc.
   - Oculto hasta que se seleccione puesto

5. **Verificación de duplicado**: al seleccionar la mesa, consultar Firestore
   inmediatamente. Si la mesa ya fue reportada mostrar un `p-message` de tipo
   `warn`: "Esta mesa ya fue reportada el [fecha] por [testigo]". Permitir
   continuar pero con advertencia visible.

6. **Tabla de candidatos** — aparece solo cuando corporación + municipio + puesto
   + mesa están seleccionados. Es una tabla `p-table` con las siguientes columnas:
   - `#` — número de orden del candidato en la lista
   - `Candidato` — nombre completo (la primera fila siempre es "Voto por lista")
   - `Votos` — `p-inputNumber` con min=0, max=9999, sin decimales

   **Comportamiento de la tabla:**
   - Primera fila siempre es la cabecera de lista (cod=000) con label "Voto por lista"
   - Resto de filas: candidatos reales ordenados por cod_candidato
   - Footer de la tabla muestra el total sumado en tiempo real
   - Los inputs deben aceptar solo enteros >= 0
   - Tab entre celdas debe funcionar naturalmente

7. **Botón "Enviar Mesa"** — deshabilitado hasta que:
   - Todos los selectores estén llenos
   - Al menos un candidato tenga votos > 0
   - El total sea > 0

**Validaciones antes de enviar:**
- Confirmar con `p-confirmDialog`: "¿Confirmas el reporte de Mesa [N] en [Puesto], [Municipio]? Total votos: [X]"
- Si el usuario confirma: construir los registros MMV, subir a Firestore, mostrar
  `p-toast` de éxito, resetear el formulario manteniendo la corporación seleccionada

**Construcción del registro MMV al enviar:**
- Por cada candidato con votos > 0, generar una línea de 38 chars
- Candidatos con 0 votos NO generan línea (optimización de espacio)
- Validar que cada línea tenga exactamente 38 chars antes de subir

### 5. `TrackingComponent` — `src/app/tracking/tracking.component`

**Vista de seguimiento en tiempo real.**

Suscripción en tiempo real a Firestore con `onSnapshot`. Muestra:

**KPIs superiores (4 cards):**
- Total mesas Antioquia (15.519 — estático del JSON)
- Mesas reportadas (conteo en tiempo real desde Firestore)
- % de avance
- Últimas 24h reportadas

**Tabla de municipios** con columnas:
- Municipio
- Mesas totales
- Mesas reportadas
- % avance
- Barra de progreso `p-progressBar`
- Click en municipio expande el detalle de puestos (p-table con rowExpansion)

**Detalle de puesto expandido:**
- Nombre del puesto
- Mesas reportadas / Total mesas
- Lista de mesas: número de mesa, estado (reportada ✓ / pendiente), hora de reporte

**Actualización**: usar `onSnapshot` de Firestore directamente (no polling).
Cuando llega un nuevo documento, actualizar solo el municipio/puesto afectado,
no rerenderizar toda la tabla.

### 6. `AuthGuard` y autenticación básica
- Firebase Authentication con email/password
- Solo usuarios autenticados pueden acceder al formulario E-14
- La vista de tracking puede ser pública
- Guardar `testigo_uid` y `testigo_email` en el documento de Firestore

---

## ROUTING

```typescript
// Agregar al router principal:
{
  path: 'e14',
  component: E14FormComponent,
  canActivate: [AuthGuard]
},
{
  path: 'tracking',
  component: TrackingComponent
}
```

---

## SIDEBAR (agregar estos items al menú existente)

```typescript
{
  label: 'Testigo Electoral',
  items: [
    {
      label: 'Reportar E-14',
      icon: 'pi pi-file-edit',
      routerLink: ['/e14']
    },
    {
      label: 'Seguimiento Mesas',
      icon: 'pi pi-chart-bar',
      routerLink: ['/tracking']
    }
  ]
}
```

---

## REGLAS DE FIRESTORE (firestore.rules)

```
rules_version = '2';
service cloud.firestore {
  match /databases/{database}/documents {
    match /mesas_reportadas/{mesaKey} {
      allow read: if true;
      allow create: if request.auth != null
        && request.resource.data.testigo_uid == request.auth.uid;
      allow update, delete: if false;  // inmutable una vez enviado
    }
    match /resumen_municipios/{municipio} {
      allow read: if true;
      allow write: if request.auth != null;
    }
  }
}
```

---

## MODELOS TypeScript

```typescript
// src/app/models/catalogo.model.ts

export interface Puesto {
  zona: string;
  cod_puesto: string;
  nombre: string;
  num_mesas: number;
}

export interface Municipio {
  cod: string;
  nombre: string;
  puestos: Puesto[];
}

export interface Candidato {
  cod_candidato: string;
  nombre_completo: string;
  es_lista: boolean;
}

export interface E14FormData {
  corporacion: 'senado' | 'camara';
  municipio: Municipio;
  puesto: Puesto;
  num_mesa: number;
  votos: { cod_candidato: string; votos: number }[];
}

export interface MesaReportada {
  mesa_key: string;
  cod_depto: string;
  cod_muni: string;
  nom_muni: string;
  zona: string;
  cod_puesto: string;
  nom_puesto: string;
  num_mesa: number;
  corporacion: string;
  corporacion_nombre: string;
  circunscripcion: string;
  cod_partido: string;
  registros_mmv: string[];
  total_votos: number;
  testigo_uid: string;
  testigo_email: string;
  timestamp: any;
  estado: 'enviado';
}
```

---

## CONSIDERACIONES TÉCNICAS

1. **Carga de assets**: usar `HttpClient` en `CatalogoService` para cargar los JSON
   desde `assets/data/`. Cargar en `APP_INITIALIZER` para que estén disponibles
   antes de que se renderice cualquier componente.

2. **Performance en dropdowns**: el dropdown de puestos puede tener hasta 250
   entradas (Medellín). Usar `virtualScroll` de PrimeNG con `virtualScrollItemSize`
   para que sea fluido.

3. **Validación del formato MMV**: antes de subir a Firestore, validar que cada
   registro tenga exactamente 38 caracteres. Si alguno falla, no subir nada y
   mostrar error específico.

4. **Deduplicación**: el ID del documento en Firestore es la `mesa_key`. Si se
   intenta subir una mesa ya existente, Firestore rechazará con error de permisos
   (las reglas no permiten update). Manejar ese error con mensaje claro al testigo.

5. **Offline**: considerar `enableIndexedDbPersistence()` de Firestore para que
   los testigos en zonas con mala conectividad puedan llenar el formulario offline
   y se sincronice automáticamente cuando recuperen señal.

6. **Standalone components**: usar Angular standalone components y signals donde
   sea posible (Angular 17+).

7. **Zona en el formulario**: la zona NO se muestra al usuario. Se obtiene
   automáticamente del objeto `Puesto` seleccionado del JSON. Es transparente.

---

## ENTREGABLES ESPERADOS

- `src/app/services/catalogo.service.ts`
- `src/app/services/firestore.service.ts`
- `src/app/services/mmv-builder.service.ts`
- `src/app/e14/e14-form/e14-form.component.ts`
- `src/app/e14/e14-form/e14-form.component.html`
- `src/app/tracking/tracking.component.ts`
- `src/app/tracking/tracking.component.html`
- `src/app/models/catalogo.model.ts`
- Modificaciones al router y al sidebar
- `firestore.rules`
