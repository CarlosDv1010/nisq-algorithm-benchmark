# Implementación y Análisis de Algoritmos Cuánticos en la Era NISQ

Trabajo de grado — Ingeniería de Sistemas y Computación, Universidad de los Andes (2026).

Este repositorio contiene el framework de benchmarking, los datos experimentales, el análisis y el documento de la tesis.

## Resumen

Estudio experimental que mide el impacto del ruido y la topología de hardware sobre cuatro algoritmos cuánticos fundamentales: **Bernstein-Vazirani**, **Simon**, **Grover sobre instancias k-SAT** y **Estimación Cuántica de Fase (QPE)**. Cada algoritmo se evaluó bajo tres modelos de ruido (error de lectura, despolarizante y relajación térmica) y tres topologías (ideal, lineal de 20 qubits y heavy-hex de 127 qubits inspirada en `ibm_brisbane`), con 25 repeticiones por escenario e intervalos de confianza al 95%.

Toda la infraestructura corre en simulación sobre **Qiskit** + **Qiskit Aer**, sin necesidad de acceso a hardware real.

## Estructura del repositorio

```
.
├── src/
│   ├── algorithms/          # Implementaciones cuánticas y clásicas
│   │   ├── bernstein_vazirani.py
│   │   ├── simon.py
│   │   ├── grover_ksat.py
│   │   └── qpe.py
│   ├── utils/               # Modelos de ruido, métricas y generador k-SAT
│   │   ├── noise_factory.py
│   │   ├── metrics.py
│   │   └── ksat_gen.py
│   ├── data/
│   │   └── run_benchmarks.py  # Script maestro del banco de pruebas
│   └── ui/                  # Interfaz interactiva (Streamlit)
│       ├── bv_view.py
│       ├── simon_view.py
│       ├── grover_view.py
│       └── qpe_view.py
├── notebooks/
│   └── analysis.py          # Genera las figuras del documento desde los CSV
├── data/                    # Resultados del benchmark (CSV por algoritmo)
├── documento/               # Fuente LaTeX de la tesis
├── app.py                   # Punto de entrada de la interfaz Streamlit
└── requirements.txt
```

## Instalación

Requiere Python 3.11 o superior.

```bash
pip install -r requirements.txt
```

## Uso

**Reproducir el benchmark completo** (~90 min en un Intel i5-10400F):

```bash
python -m src.data.run_benchmarks
```

Los resultados se guardan en `data/benchmark_<algoritmo>_<timestamp>.csv`.

Para correr solo un subconjunto de algoritmos, editar `RUN_CONFIG` al inicio de `run_benchmarks.py`.

**Regenerar las figuras del documento**:

```bash
python notebooks/analysis.py
```

Detecta automáticamente el CSV más reciente de cada algoritmo y guarda las figuras en `documento/figures/`.

**Explorar resultados de forma interactiva**:

```bash
streamlit run app.py
```

## Dependencias principales

| Paquete | Versión mínima | Uso |
|---------|---------------|-----|
| qiskit | 1.0.0 | Construcción y transpilación de circuitos |
| qiskit-aer | 0.14.0 | Simulación con modelos de ruido |
| qiskit-ibm-runtime | 0.20.0 | FakeBrisbane (topología heavy-hex) |
| numpy / pandas / scipy | — | Análisis estadístico |
| matplotlib / seaborn | — | Visualización |
| streamlit | 1.32.0 | Interfaz exploratoria |
