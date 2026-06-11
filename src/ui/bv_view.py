import random

import matplotlib.pyplot as plt
import streamlit as st

from src.algorithms.bernstein_vazirani import BernsteinVaziraniSolver, BVBenchmarker


NOISE_TYPES = {
    "Ideal (sin ruido)": "ideal",
    "Solo error de lectura": "readout_only",
    "Despolarizante": "depolarizing",
    "Relajación térmica (T1/T2)": "thermal",
}


def render():
    st.title("Algoritmo de Bernstein-Vazirani")
    st.markdown(
        "Encuentra una cadena binaria oculta con **una sola consulta** al oráculo cuántico, "
        "mientras que la versión clásica necesita tantas consultas como bits tenga el secreto."
    )

    st.header("Configuración del experimento")

    col1, col2 = st.columns(2)
    with col1:
        n_bits = st.slider("Bits del secreto (n)", 2, 12, 4)
        peor_caso = st.checkbox(
            "Usar peor caso (todos '1')",
            value=True,
            help="El secreto de puros 1s maximiza las compuertas CX en el circuito.",
        )

    with col2:
        noise_level = st.slider(
            "Nivel de ruido",
            0.0, 0.10, 0.0,
            step=0.01,
            format="%.2f",
            help="0.0 es simulación ideal. 0.05 equivale a un 5% de error en las compuertas de 2 qubits.",
        )
        repeats = st.number_input(
            "Repeticiones estadísticas", 1, 50, 5,
            help="Número de corridas para estimar la fidelidad. Para análisis robustos se usan 100+.",
        )

    noise_label = st.selectbox(
        "Modelo de ruido",
        list(NOISE_TYPES.keys()),
        index=2,
        disabled=(noise_level <= 0.0),
        help=(
            "Ideal: sin errores. "
            "Solo lectura: errores únicamente en la medición. "
            "Despolarizante: modelo estándar con errores en compuertas y medición. "
            "Relajación térmica: simula los tiempos T1/T2 de un procesador IBM."
        ),
    )
    noise_type = NOISE_TYPES[noise_label]

    if noise_level <= 0.0 and noise_type != "ideal":
        st.caption("El modelo de ruido sólo surte efecto cuando el nivel de ruido es mayor que 0.")

    if peor_caso:
        secret = "1" * n_bits
    else:
        secret = "".join(random.choice("01") for _ in range(n_bits))
        if "1" not in secret:
            secret = "1" + secret[1:]

    st.info(f"Secreto a descubrir: `{secret}`")

    st.subheader("Circuito cuántico")
    qc = BernsteinVaziraniSolver.build_quantum_circuit(secret)
    fig, ax = plt.subplots(figsize=(max(6, n_bits), max(4, n_bits * 0.5)))
    qc.draw("mpl", ax=ax)
    st.pyplot(fig)

    st.markdown("---")
    if not st.button("Ejecutar simulación", use_container_width=True):
        return

    with st.spinner(f"Transpilando circuito y ejecutando {repeats} corridas..."):
        benchmarker = BVBenchmarker(shots=1000, repeats=repeats)
        resultados = benchmarker.run_experiment(
            secret=secret, noise_level=noise_level, noise_type=noise_type
        )

    st.success("Simulación completada.")

    st.subheader("Consultas al oráculo: clásico vs. cuántico")
    c1, c2, c3 = st.columns(3)
    c1.metric("Consultas clásicas", f"{resultados['classic_queries']}")
    c2.metric(
        "Consultas cuánticas",
        "1",
        delta=f"-{resultados['classic_queries'] - 1}",
    )
    c3.metric("Fidelidad", f"{resultados['mean']:.2f}%")

    st.subheader("Métricas del circuito transpilado")
    h1, h2, h3 = st.columns(3)
    h1.metric("Profundidad", resultados["transpiled_depth"])
    h2.metric("Compuertas CX", resultados["cx_gates"])

    if noise_level > 0.0:
        h3.metric("IC 95%", f"± {resultados['ci_margin']:.2f}%")
        st.warning(
            f"Con {noise_level * 100:.0f}% de ruido usando el modelo **{noise_label.lower()}**, "
            f"la probabilidad de recuperar el secreto bajó a **{resultados['mean']:.2f}%**. "
            f"Las {resultados['cx_gates']} compuertas CX son el principal punto de falla."
        )
    else:
        h3.metric("Condiciones", "Simulación ideal")
