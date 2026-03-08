"""
app.py — Dashboard Electoral CREEMOS
══════════════════════════════════════
Entry point. Toda la lógica vive en pages/.

  pages/shared.py                → constantes, estilos, helpers, carga de datos
  pages/sidebar.py               → navegación lateral
  pages/pg_dashboard.py          → Overview general
  pages/pg_candidatos_general.py → Explorador de todos los candidatos
  pages/pg_candidato.py          → Detalle candidato individual (German / Juliana)
  pages/pg_partidos.py           → Partidos Senado & Cámara Antioquia
  pages/pg_geografico.py         → Análisis geográfico con 3 filtros
  pages/pg_cruce_votos.py        → Cruce testigos vs oficial

Para correr:
    pip install -r requirements.txt
    streamlit run app.py
"""

from __future__ import annotations

import time
import streamlit as st

st.set_page_config(
    page_title="Dashboard Electoral · CREEMOS",
    page_icon="data:image/svg+xml,<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24' fill='%23E63946'><path d='M18 3H6C4.9 3 4 3.9 4 5v14c0 1.1.9 2 2 2h12c1.1 0 2-.9 2-2V5c0-1.1-.9-2-2-2zm-5 14H7v-2h6v2zm4-4H7v-2h10v2zm0-4H7V7h10v2z'/></svg>",
    layout="wide",
    initial_sidebar_state="expanded",
)

from pages.shared import inject_styles, cargar_todo, DATA_DIR, resolver_mmv_path
from pages.sidebar import render_sidebar
import pages.pg_dashboard as pg_dashboard
import pages.pg_curules_senado as pg_curules_senado
import pages.pg_curules_camara_antioquia as pg_curules_camara_antioquia
import pages.pg_candidatos_general as pg_candidatos
import pages.pg_candidato as pg_candidato
import pages.pg_partidos as pg_partidos
import pages.pg_geografico as pg_geografico
import pages.pg_cruce_votos as pg_cruce_votos
import pages.pg_mesas_sin_votos as pg_mesas_sin_votos


def main():
    inject_styles()

    mmv_path = resolver_mmv_path()
    files = [
        mmv_path.name,
        "CANDIDATOS.txt",
        "PARTIDOS.txt",
        "DIVIPOL.txt",
        "CORPORACION.txt",
    ]
    sig_parts = []
    for fname in files:
        p = DATA_DIR / fname
        if p.exists():
            stt = p.stat()
            sig_parts.append(f"{fname}:1:{stt.st_size}:{stt.st_mtime_ns}")
        else:
            sig_parts.append(f"{fname}:0")
    cache_key = "|".join(sig_parts)

    first_boot = not st.session_state.get("_data_boot_ok", False)
    if first_boot:
        load_box = st.empty()
        load_box.info("Cargando datos electorales...")
        with st.spinner("Cargando datos electorales..."):
            datos = cargar_todo(cache_key)
            # Evita que el indicador desaparezca demasiado rápido al primer arranque.
            time.sleep(0.25)
        if datos.get("mmv"):
            src = datos["mmv"].get("cache_meta", {}).get("load_source", "")
            if src == "parquet":
                load_box.success("Datos cargados (caché Parquet).")
            elif src == "txt":
                load_box.success("Datos cargados (parseo TXT).")
            else:
                load_box.success("Datos cargados.")
        else:
            load_box.warning(f"Datos parciales: no se encontró MMV en {mmv_path}.")
        st.session_state["_data_boot_ok"] = True
    else:
        datos = cargar_todo(cache_key)

    page = render_sidebar(datos)

    if page == "dashboard":
        pg_dashboard.render(datos)

    elif page == "curules_senado":
        pg_curules_senado.render(datos)

    elif page == "curules_camara_antioquia":
        pg_curules_camara_antioquia.render(datos)

    elif page == "candidatos":
        pg_candidatos.render(datos)

    elif page == "german":
        pg_candidato.render(
            datos,
            cand_key="01067_117",
            nombre="GERMAN DARIO HOYOS GIRALDO",
            cargo="Cámara",
            color="#2196F3",
            solo_antioquia=True,
            expected_corporacion="002",
            expected_circ="1",
            expected_depto="01",
        )

    elif page == "juliana":
        pg_candidato.render(
            datos,
            cand_key="01070_001",
            nombre="JULIANA GUTIERREZ ZULUAGA",
            cargo="Senado",
            color="#E63946",
            solo_antioquia=False,
            expected_corporacion="001",
            expected_circ="0",
        )

    elif page == "partidos":
        pg_partidos.render(datos)

    elif page == "geografico":
        pg_geografico.render(datos)

    elif page == "cruce_votos":
        pg_cruce_votos.render(datos)

    elif page == "mesas_sin_votos":
        pg_mesas_sin_votos.render(datos)


if __name__ == "__main__":
    main()
