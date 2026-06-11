import matplotlib.pyplot as plt
import streamlit as st

from src.algorithms.qpe import QPESolver, QPEBenchmarker


NOISE_TYPES = {
    "Ideal (sin ruido)": "ideal",
    "Solo error de lectura": "readout_only",
    "Despolarizante": "depolarizing",
    "Relajación térmica (T1/T2)": "thermal",
}


def render():
    st.title("Algoritmo de Estimación de Fase Cuántica (QPE)")
    st.markdown(
        r"QPE aproxima la fase $\theta$ en el autovalor $e^{2\pi i \theta}$. "
        r"La precisión depende de $n$ qubits, alcanzando una resolución de $1/2^n$."
    )

    st.header("Configuración del experimento")

    col1, col2 = st.columns(2)
    with col1:
        n_bits = st.slider(
            "Qubits de precisión (n)", 2, 7, 3,
            help="Determina la resolución binaria de la fase.",
        )
        theta = st.number_input(
            "Fase real (θ)", min_value=0.0, max_value=1.0, value=0.375, step=0.001,
            help="Valores como 0.375 (3/8) son exactos para n=3.",
        )

    with col2:
        noise_level = st.slider("Nivel de ruido", 0.0, 0.10, 0.0, step=0.01, format="%.2f")
        repeats = st.number_input("Repeticiones estadísticas", 1, 100, 10)

    noise_label = st.selectbox(
        "Modelo de ruido",
        list(NOISE_TYPES.keys()),
        index=2,
        disabled=(noise_level <= 0.0),
    )
    noise_type = NOISE_TYPES[noise_label]

    st.subheader("Inspección del circuito cuántico")
    with st.expander("Configurar visualización del circuito", expanded=True):
        col_v1, col_v2 = st.columns(2)
        with col_v1:
            descomponer = st.toggle(
                "Descomponer compuertas", value=False,
                help="Muestra el circuito tras la transpilación a la base {u, cx}.",
            )
        with col_v2:
            fold_val = st.slider("Ancho de plegado (fold)", 5, 50, 15 if n_bits < 5 else 10)

    qc = QPESolver.build_quantum_circuit(theta, n_bits)
    if descomponer:
        qc = qc.decompose()

    fig_height = max(4, (n_bits * 0.8) + (qc.depth() / fold_val * 2))
    fig, ax = plt.subplots(figsize=(12, fig_height))
    qc.draw("mpl", ax=ax, scale=0.8, fold=fold_val)
    st.pyplot(fig)

    st.markdown("---")
    if st.button("Ejecutar benchmark de QPE", use_container_width=True):
        with st.spinner("Simulando en entorno NISQ..."):
            benchmarker = QPEBenchmarker(repeats=repeats)
            st.session_state["qpe_res"] = benchmarker.run_experiment(
                theta, n_bits, noise_level, noise_type
            )

    if "qpe_res" not in st.session_state:
        return

    res = st.session_state["qpe_res"]

    st.subheader("Rendimiento del algoritmo")
    c1, c2, c3 = st.columns(3)
    c1.metric("Fase real", f"{theta:.4f}")
    c2.metric(
        "Mejor aproximación",
        f"{res['theta_discretizado']:.4f}",
        delta=f"{res['theta_discretizado'] - theta:.4f}",
        delta_color="off",
    )
    c3.metric("Fidelidad de medición", f"{res['mean']:.2f}%")

    st.subheader("Costo de hardware (circuito transpilado)")
    h1, h2, h3 = st.columns(3)
    h1.metric("Profundidad", res["transpiled_depth"])
    h2.metric("Compuertas CX", res["cx_gates"])

    if noise_level > 0:
        h3.metric("IC 95%", f"± {res['ci_margin']:.2f}%")
        st.warning(
            f"**Análisis NISQ:** con {noise_level * 100:.0f}% de ruido ({noise_label.lower()}) "
            f"la fidelidad es de **{res['mean']:.2f}%**. La profundidad de "
            f"**{res['transpiled_depth']}** es crítica: en QPE cada qubit extra de precisión "
            f"duplica las rotaciones controladas, por lo que la fidelidad cae rápido al crecer n."
        )
    else:
        h3.metric("Estado", "Simulación ideal")
