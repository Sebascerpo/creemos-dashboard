# PROMPT — Página "Cruce Testigos vs Oficial" en Streamlit

## QUÉ ES ESTA PÁGINA

Módulo de análisis electoral que cruza dos fuentes de datos:

1. **Votos de testigos** — reportados por el partido CREEMOS desde campo a través
   de una app Angular. Cada mesa reportada contiene los votos del E-14 físico
   (formulario oficial de conteo por mesa). Estos datos viven en Firestore.

2. **Votos oficiales** — el archivo MMV de la Registraduría (boletín oficial),
   ya parseado y disponible en memoria.

El objetivo es detectar discrepancias entre ambas fuentes, entender si son
errores aleatorios o patrones sistemáticos, y determinar si afectan el resultado
electoral del partido.

---

## SECCIÓN 1 — COBERTURA

Antes de cruzar, mostrar claramente qué porcentaje del universo de mesas
está disponible para el análisis.

Lo que quiero ver:

- Cuántas mesas tienen reporte de testigo
- Cuántas mesas están en el boletín oficial
- Cuántas mesas tienen AMBAS fuentes (las únicas que se pueden cruzar)
- Porcentaje de cobertura sobre el total oficial
- Distribución geográfica: qué municipios tienen buena cobertura y cuáles no
- Una alerta visual si la cobertura es muy baja (no es confiable cruzar)
- Una alerta de éxito si la cobertura es alta (cruce confiable)

---

## SECCIÓN 2 — DISCREPANCIAS

Para cada mesa que aparece en ambas fuentes, cruzar voto por voto y candidato
por candidato. La discrepancia es: votos testigo − votos oficial.

**Discrepancia positiva** (testigo reporta MÁS que el oficial):
El boletín oficial tiene menos votos de los que el testigo contó en el E-14.
Esto puede indicar que votos fueron sustraídos en el escrutinio.

**Discrepancia negativa** (testigo reporta MENOS que el oficial):
El boletín oficial tiene más votos de los que el testigo contó en el E-14.
Esto puede indicar que votos fueron adicionados en el escrutinio.

**Coincidencia exacta**: sin diferencia.

Lo que quiero ver:

- KPIs: total mesas cruzadas, mesas con coincidencia, mesas con discrepancia
  positiva, mesas con discrepancia negativa
- Tabla de discrepancias positivas ordenada por magnitud (más grave primero)
- Tabla de discrepancias negativas ordenada por magnitud (más grave primero)
- Tabla de coincidencias (mesas verificadas)
- Resumen por candidato: votos testigo total, votos oficial total, diferencia acumulada
- Separación clara entre Senado y Cámara

---

## SECCIÓN 3 — ANÁLISIS DE PATRONES

Los errores humanos son aleatorios: aparecen dispersos, en ambas direcciones,
con magnitudes variables. El fraude sistemático tiene patrón: se concentra en
zonas específicas, va en una sola dirección, con magnitudes similares.

Lo que quiero ver:

**Distribución de discrepancias:**
Un histograma que muestre si las diferencias están simétricamente distribuidas
alrededor de cero (probable error humano) o si están sesgadas hacia un lado
(patrón sistemático).

**Concentración geográfica:**
¿Las discrepancias se concentran en municipios o puestos específicos?
Un municipio con el 80% de sus mesas con discrepancia es muy distinto a
discrepancias dispersas en todo Antioquia.

**Consistencia por puesto:**
Si un puesto de votación tiene múltiples mesas y todas van en la misma
dirección, eso es una señal fuerte. Quiero ver alertas cuando esto ocurra.

**Sesgo direccional:**
¿Qué porcentaje de las discrepancias son positivas vs negativas?
Si más del 70% van en la misma dirección, hay sesgo sistemático.

---

## SECCIÓN 4 — IMPACTO ACUMULADO

La pregunta que más importa: ¿las discrepancias cambian el resultado electoral?

Lo que quiero ver:

**Por candidato:**
Para Juliana (Senado) y Germán (Cámara):

- Votos totales según testigos
- Votos totales según boletín oficial
- Diferencia acumulada
- Si la diferencia es material o insignificante

**Impacto en el umbral del Senado (3%):**

- ¿Con los votos oficiales CREEMOS pasa el umbral?
- ¿Con los votos de los testigos CREEMOS pasa el umbral?
- Si son diferentes, ¿cuántos votos separan ambos escenarios del umbral?
- Proyección: si la discrepancia encontrada se repite proporcionalmente en
  las mesas que aún no tienen testigo, ¿cambia el resultado?

**Impacto en curules (D'Hondt):**

- ¿Con los votos del testigo CREEMOS obtendría más o menos curules que con
  los votos oficiales?
- Mostrar ambos escenarios del reparto de curules lado a lado

**Alerta de materialidad:**
Si la discrepancia acumulada es lo suficientemente grande para cambiar
algún resultado concreto (umbral o curul), resaltarlo con alerta prominente.

---

## SECCIÓN 5 — LISTA DE ACCIÓN JURÍDICA

Insumo directo para el equipo legal. Lista priorizada de mesas a impugnar.

Lo que quiero ver:

**Criterios de prioridad:**
No todas las discrepancias valen igual. Las más prioritarias son:

- Mayor magnitud absoluta de la discrepancia
- Puestos donde todas las mesas tienen discrepancia en la misma dirección
- Discrepancias positivas (el partido perdió votos) sobre negativas
- Mesas donde hay un testigo identificado (tiene valor probatorio)

**Tabla priorizada:**
Todas las mesas con discrepancia, ordenadas por prioridad, con:

- Municipio, puesto, número de mesa
- Candidato afectado
- Votos según testigo vs votos oficiales
- Diferencia
- Email del testigo que reportó
- Nivel de prioridad (alta / media / baja)

**Filtros sobre la tabla:**

- Por corporación (Senado / Cámara)
- Por dirección de discrepancia (positiva / negativa)
- Por municipio
- Por umbral mínimo de diferencia

**Exportación:**

- CSV con toda la lista para el equipo jurídico
- Excel con varias hojas: lista completa, resumen por municipio, resumen
  por candidato
