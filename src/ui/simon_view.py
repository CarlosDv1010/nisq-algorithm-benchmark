import matplotlib.pyplot as plt
import streamlit as st

from src.algorithms.simon import SimonSolver, SimonBenchmarker


NOISE_TYPES = {
    "Ideal (sin ruido)": "ideal",
    "Solo error de lectura": "readout_only",
    "Despolarizante": "depolarizing",
    "Relajación térmica (T1/T2)": "thermal",
}


def render():
    st.title("Algoritmo de Simon")
    st.markdown(
        "Simon fue el primer algoritmo en demostrar una **separación exponencial** entre la "
        "computación clásica y la cuántica. El circuito muestrea ecuaciones lineales y una CPU "
        "clásica resuelve el sistema resultante sobre GF(2)."
    )

    st.header("Configuración del experimento")

    col1, col2 = st.columns(2)
    with col1:
        n_bits = st.slider(
            "Longitud del secreto (n)", 2, 6, 3,
            help="Tamaño del secreto s. El oráculo actúa sobre 2n qubits.",
        )
        secreto_sugerido = "1" * (n_bits - 1) + "0"
        secret = st.text_input("Secreto oculto (s)", value=secreto_sugerido, max_chars=n_bits)

        if len(secret) != n_bits or not all(c in "01" for c in secret):
            st.error(f"El secreto debe ser una cadena binaria de exactamente {n_bits} bits.")
            st.stop()

    with col2:
        noise_level = st.slider(
            "Nivel de ruido", 0.0, 0.10, 0.0,
            step=0.01,
            format="%.2f",
            help="En Simon, un solo bit de error puede corromper el sistema GF(2).",
        )
        repeats = st.number_input(
            "Intentos del protocolo híbrido", 1, 50, 5,
            help="Cuántas veces se intenta resolver el sistema GF(2) completo.",
        )

    noise_label = st.selectbox(
        "Modelo de ruido",
        list(NOISE_TYPES.keys()),
        index=2,
        disabled=(noise_level <= 0.0),
    )
    noise_type = NOISE_TYPES[noise_label]

    if noise_level <= 0.0 and noise_type != "ideal":
        st.caption("El modelo de ruido sólo surte efecto cuando el nivel de ruido es mayor que 0.")

    st.info(f"Función 2-a-1 configurada para el secreto: `{secret}`")

    st.subheader("Oráculo y circuito cuántico (2n qubits)")
    qc = SimonSolver.build_quantum_circuit(secret)
    fig, ax = plt.subplots(figsize=(max(8, n_bits * 1.5), max(5, n_bits)))
    qc.draw("mpl", ax=ax)
    st.pyplot(fig)

    st.markdown("---")
    if not st.button("Ejecutar protocolo de Simon", use_container_width=True):
        return

    st.info("Muestreando vectores z ortogonales a s…")

    with st.spinner(f"Transpilando y ejecutando {repeats} intentos del protocolo híbrido..."):
        benchmarker = SimonBenchmarker(repeats=repeats)
        resultados = benchmarker.run_experiment(
            secret=secret, noise_level=noise_level, noise_type=noise_type
        )

    st.success("Protocolo completado.")

    st.subheader("Consultas al oráculo: clásico vs. cuántico")
    c1, c2, c3 = st.columns(3)
    c1.metric("Fuerza bruta clásica", f"{resultados['classic_queries']}")
    c2.metric(
        "Muestreo cuántico",
        f"{resultados['quantum_queries']}",
        delta=f"-{resultados['classic_queries'] - resultados['quantum_queries']}",
    )
    c3.metric("Éxito en GF(2)", f"{resultados['mean']:.2f}%")

    st.subheader("Métricas del circuito transpilado")
    h1, h2, h3 = st.columns(3)
    h1.metric("Profundidad", resultados["transpiled_depth"])
    h2.metric("Compuertas CX", resultados["cx_gates"])

    if noise_level > 0.0:
        h3.metric("IC 95%", f"± {resultados['ci_margin']:.2f}%")
        st.warning(
            f"Con {noise_level * 100:.0f}% de ruido ({noise_label.lower()}), la tasa de éxito "
            f"cayó a **{resultados['mean']:.2f}%**. En Simon, un solo bit de error en la "
            f"medición entrega un vector z incorrecto y el sistema GF(2) queda sin solución. "
            f"Las {resultados['cx_gates']} compuertas CX son el principal punto de falla."
        )
    else:
        h3.metric("Condiciones", "Simulación ideal")
