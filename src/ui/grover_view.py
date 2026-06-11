import matplotlib.pyplot as plt
import numpy as np
import streamlit as st

from src.algorithms.grover_ksat import KSATSolver, GroverBenchmarker
from src.utils.ksat_gen import KSATGenerator


NOISE_TYPES = {
    "Ideal (sin ruido)": "ideal",
    "Solo error de lectura": "readout_only",
    "Despolarizante": "depolarizing",
    "Relajación térmica (T1/T2)": "thermal",
}


def _buscar_formula_con_soluciones(n_vars: int, n_clauses: int, k_val: int, max_intentos: int = 25):
    """Genera fórmulas aleatorias hasta hallar una satisfacible (idealmente con pocas soluciones)."""
    limite_ideal = max(1, int(np.sqrt(2**n_vars)))
    mejor_expr = ""
    for intento in range(1, max_intentos + 1):
        expr = KSATGenerator.generate_random_cnf(n_vars, n_clauses, k_val)
        soluciones, _ = KSATSolver.solve_classical(n_vars, expr)
        if soluciones:
            mejor_expr = expr
            if len(soluciones) <= limite_ideal:
                return mejor_expr, intento
    return mejor_expr, max_intentos


def render():
    st.title("Algoritmo de Grover aplicado a k-SAT")
    st.markdown(
        "k-SAT es un problema NP-Completo. Grover ofrece una **aceleración cuadrática** "
        "construyendo un oráculo de fase a partir de una fórmula lógica en formato CNF."
    )

    st.header("Configuración del problema")

    col1, col2 = st.columns(2)
    with col1:
        n_vars = st.slider("Número de variables (n)", 2, 6, 3, help="Tamaño del espacio de búsqueda: 2^n.")
        modo_input = st.radio("Modo de fórmula", ("Generar aleatoria", "Ingresar manualmente"))

        if modo_input == "Generar aleatoria":
            k_val = st.slider("Tamaño de cláusula (k)", 2, n_vars, min(3, n_vars))
            n_clauses = st.slider("Número de cláusulas (m)", 1, 30, n_vars * 2)

            if st.button("Generar nueva fórmula k-SAT"):
                with st.spinner("Buscando instancia válida..."):
                    expr, intentos = _buscar_formula_con_soluciones(n_vars, n_clauses, k_val)
                    if expr:
                        st.session_state["expr_ksat"] = expr
                        st.toast(f"Fórmula generada en {intentos} intento(s).", icon="✅")
                    else:
                        st.error("No se halló una fórmula con soluciones. Prueba bajando 'm'.")

            expression = st.session_state.get("expr_ksat", "(v0 | ~v1) & (v1 | ~v2)")
        else:
            expression = st.text_input(
                "Fórmula lógica (formato Qiskit)",
                value="(v0 | ~v1) & (~v0 | v2)",
            )

    with col2:
        noise_level = st.slider("Nivel de ruido", 0.0, 0.10, 0.0, step=0.01, format="%.2f")
        repeats = st.number_input("Repeticiones estadísticas", 1, 50, 5)
        noise_label = st.selectbox(
            "Modelo de ruido",
            list(NOISE_TYPES.keys()),
            index=2,
            disabled=(noise_level <= 0.0),
        )
        noise_type = NOISE_TYPES[noise_label]

    try:
        soluciones_validas, _ = KSATSolver.solve_classical(n_vars, expression)
    except Exception as e:
        st.error(f"Error en la fórmula lógica: {e}")
        st.stop()

    num_soluciones = len(soluciones_validas)
    st.info(f"Fórmula actual: `{expression}`")

    with st.expander("Ver detalles de satisfacibilidad"):
        st.write(f"Espacio de búsqueda total: $2^{n_vars} = {2**n_vars}$ combinaciones.")
        if num_soluciones == 0:
            st.error("Esta fórmula es insatisfacible (0 soluciones). Grover no puede ejecutarse.")
            st.stop()
        st.success(f"Fórmula satisfacible con {num_soluciones} solución(es) válida(s).")
        st.write(f"Soluciones (little-endian): {soluciones_validas}")

    st.markdown("---")
    if st.button("Compilar oráculo y ejecutar Grover", use_container_width=True):
        with st.spinner("Transpilando oráculo y ejecutando iteraciones..."):
            benchmarker = GroverBenchmarker(repeats=repeats)
            res = benchmarker.run_experiment(
                name="UI_KSAT",
                expression=expression,
                num_vars=n_vars,
                noise_level=noise_level,
                noise_type=noise_type,
            )
            st.session_state["last_res"] = res
            st.session_state["last_expr"] = expression

    if st.session_state.get("last_expr") != expression:
        st.session_state.pop("last_res", None)

    if "last_res" not in st.session_state:
        return

    res = st.session_state["last_res"]
    iteraciones = res["quantum_queries"]

    # Probabilidad teórica según la amplificación de amplitud de Grover
    prob_teorica = (
        np.sin((2 * iteraciones + 1) * np.arcsin(np.sqrt(num_soluciones / 2**n_vars))) ** 2
    ) * 100

    st.subheader("Resultados y comparación")
    if iteraciones == 0:
        st.warning(f"Demasiadas soluciones ({num_soluciones}). Grover usaría 0 iteraciones.")

    c1, c2, c3 = st.columns(3)
    c1.metric("Evaluaciones clásicas", f"{res['classic_queries']}")
    c2.metric(
        "Iteraciones Grover",
        f"{iteraciones}",
        delta=f"-{res['classic_queries'] - iteraciones}",
    )
    if noise_level <= 0.0:
        c3.metric("Probabilidad teórica ideal", f"{prob_teorica:.1f}%")
    else:
        c3.metric("Fidelidad simulada", f"{res['mean']:.2f}%")

    st.subheader("Métricas del circuito transpilado")
    h1, h2, h3 = st.columns(3)
    h1.metric("Profundidad", res["transpiled_depth"])
    h2.metric("Compuertas CX", res["cx_gates"])

    if noise_level > 0.0:
        h3.metric("IC 95%", f"± {res['ci_margin']:.2f}%")
        st.warning(
            f"**Análisis NISQ:** con {noise_level * 100:.0f}% de ruido ({noise_label.lower()}) "
            f"la fidelidad cayó a **{res['mean']:.2f}%**. El oráculo generó {res['cx_gates']} "
            f"compuertas CX; la decoherencia acumulada en las {iteraciones} iteraciones "
            f"erosiona la ventaja cuántica."
        )
    else:
        h3.metric("Estado", "Simulación ideal")

    st.markdown("---")
    with st.expander("Inspección del circuito"):
        if st.checkbox("Mostrar diagrama del circuito"):
            descomponer = st.toggle(
                "Descomponer bloques (ver todas las compuertas)", value=False
            )
            qc = KSATSolver.build_quantum_circuit(expression, n_vars, iteraciones)
            diagrama = qc.decompose() if descomponer else qc
            fig, ax = plt.subplots(figsize=(12, 6))
            diagrama.draw("mpl", ax=ax, scale=0.8, fold=-1)
            st.pyplot(fig)
