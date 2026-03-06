# Dashboard Electoral — CREEMOS

Dashboard de monitoreo de votos en tiempo real para las elecciones.
Lee archivos TXT directamente y genera caché Parquet de agregados para acelerar carga.

## Estructura

```
electoral-dashboard/
  ├── app.py                    ← App principal Streamlit
  ├── core/
  │   ├── parser.py             ← Parseo y agregación del MMV
  │   └── (cache Parquet)       ← data/cache_parquet/<archivo_mmv>/
  │   └── catalogos.py          ← Carga PARTIDOS, CANDIDATOS, DIVIPOL
  ├── data/
  │   ├── PPP_MMV_DD_9999.txt   ← ⭐ REEMPLAZAR con cada nuevo boletín
  │   ├── PARTIDOS.txt
  │   ├── CANDIDATOS.txt
  │   ├── DIVIPOL.txt
  │   └── CORPORACION.txt
  └── requirements.txt
```

## Correr localmente

```bash
pip install -r requirements.txt
streamlit run app.py
```

## Carga rápida con Parquet (recomendado)

- En el primer arranque, `core/parser.py` parsea el TXT y guarda caché Parquet.
- En siguientes arranques, carga directo desde Parquet si el TXT no cambió (`size + mtime`).
- Ubicaciones usadas:
  - `data/cache_parquet/<nombre_archivo_mmv>/`
  - fallback: `/tmp/electoral-dashboard-cache/<nombre_archivo_mmv>/`

Si actualizas `PPP_MMV_DD_9999.txt`, el caché se invalida automáticamente y se reconstruye.

Para precalentar caché antes de subir/deploy:

```bash
python scripts/prewarm_parquet_cache.py --mmv data/PPP_MMV_DD_9999.txt
```

Importante para Streamlit Cloud:
- Si no existe `data/cache_parquet/...` en el repo, el primer arranque intentará parsear el TXT completo y puede caerse por memoria/tiempo.
- Recomendado: generar caché local con el script, confirmar carpeta `data/cache_parquet/PPP_MMV_DD_9999/` y subirla a GitHub junto con el código.

## Deploy en Streamlit Cloud

1. Sube este repo a GitHub
2. Ve a https://share.streamlit.io
3. Conecta el repo → selecciona `app.py`
4. Deploy

## Actualizar datos (nuevo boletín)

```bash
# Reemplaza el archivo MMV con el nuevo boletín
cp /ruta/nuevo/PPP_MMV_DD_9999.txt data/PPP_MMV_DD_9999.txt

# Sube a GitHub → Streamlit Cloud redespliega automático
git add data/PPP_MMV_DD_9999.txt
git commit -m "Boletín #2 - XX:XX horas"
git push
```

## Candidatos principales trackeados

Configurados en `app.py` en la variable `CANDIDATOS_PRINCIPALES`:

- **JULIANA GUTIERREZ ZULUAGA** — Senado — partido `01070` candidato `001`
- **GERMAN DARIO HOYOS GIRALDO** — Cámara — partido `01067` candidato `117`

Para agregar más candidatos, edita `CANDIDATOS_PRINCIPALES` en `app.py`.

## Páginas del dashboard

| Página | Descripción |
|---|---|
| 📊 Dashboard | KPIs generales, top candidatos, top partidos |
| 🧑 Candidatos | Drill-down por candidato, votos por depto/municipio |
| 🏛️ Partidos | Ranking partidos, distribución geográfica |
| 🗺️ Geográfico | Análisis por depto y municipio, % participación |
| 👁️ Testigos | Ingreso manual de reportes de campo y cruce con oficial |
| 📋 Exportar | Descarga CSV de candidatos, partidos, municipios, deptos |
