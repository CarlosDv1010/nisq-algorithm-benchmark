import streamlit as st
from src.ui import bv_view, simon_view, grover_view, qpe_view

st.set_page_config(
    page_title="Algoritmos Clásicos en Computación Cuántica",
    page_icon="⚛️",
    layout="wide",
    initial_sidebar_state="expanded"
)

# --- ESTILOS ---
st.markdown("""
    <style>
        .sidebar-title {
            text-align: center;
            font-size: 22px;
            font-weight: bold;
            margin-top: 10px;
        }
        .sidebar-footer {
            text-align: center;
            font-size: 13px;
            color: gray;
        }
    </style>
""", unsafe_allow_html=True)

with st.sidebar:
    col1, col2, col3 = st.columns([1,2,1])
    with col2:
        st.image(
            "https://upload.wikimedia.org/wikipedia/commons/5/51/Qiskit-Logo.svg",
            use_container_width=True
        )

    st.markdown('<div class="sidebar-title">Navegación</div>', unsafe_allow_html=True)
    st.markdown("---")

    algoritmo = st.radio(
        "Seleccione el algoritmo:",
        ("Bernstein-Vazirani", "Algoritmo de Simon", "Grover (k-SAT)", "Algoritmo de Estimación de Fase (QPE)")
    )

    st.markdown("---")

    st.markdown(
        '<div class="sidebar-footer">Proyecto de Grado<br>Ingeniería de Sistemas<br><i>Era NISQ</i></div>',
        unsafe_allow_html=True
    )

if algoritmo == "Bernstein-Vazirani":
    bv_view.render()
elif algoritmo == "Algoritmo de Simon":
    simon_view.render()
elif algoritmo == "Grover (k-SAT)":
    grover_view.render()
elif algoritmo == "Algoritmo de Estimación de Fase (QPE)":
    qpe_view.render()