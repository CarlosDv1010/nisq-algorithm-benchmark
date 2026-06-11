"""
Script maestro del banco de pruebas.

Ejecuta los cuatro algoritmos (Bernstein-Vazirani, Simon, Grover k-SAT y QPE)
variando topología de hardware, modelo de ruido, nivel de ruido y tamaño de
entrada. Cada experimento se repite varias veces para obtener estadística
descriptiva (media, desviación e intervalo de confianza al 95%).

Cada algoritmo escribe en su propio CSV (uno por algoritmo, todos compartiendo
la misma marca de tiempo) para evitar problemas de columnas heterogéneas.
"""

import csv
import os
from datetime import datetime

from tqdm import tqdm

from src.algorithms.bernstein_vazirani import BVBenchmarker
from src.algorithms.simon import SimonBenchmarker
from src.algorithms.grover_ksat import GroverBenchmarker, KSATSolver
from src.algorithms.qpe import QPEBenchmarker
from src.utils.ksat_gen import KSATGenerator


# Qué algoritmos incluir en la corrida (poner False para omitir alguno)
RUN_CONFIG = {
    "BV": True,
    "SIMON": True,
    "GROVER": True,
    "QPE": True,
}

# Repeticiones por experimento (25 da IC95 sólido con t-Student sin explotar los tiempos)
REPEATS = 25
SHOTS = 1024

# Grover con k=4 es más costoso; se le baja un poco la repetición pero se mantiene estadística decente.
GROVER_K4_REPEATS = 12

# Topologías de hardware evaluadas
TOPOLOGIES = ["ideal", "line", "heavy-hex"]

# Modelos de ruido físico (el caso ideal se corre aparte una sola vez)
NOISE_TYPES = ["readout_only", "depolarizing", "thermal"]
NOISE_LEVELS = [0.02, 0.05, 0.08, 0.10]

# Rangos de escalabilidad
N_RANGE_LINEAR = [2, 3, 4, 5, 6, 7]   # BV y QPE (separación polinomial / precisión)
N_RANGE_EXP = [2, 3, 4, 5, 6]         # Simon y Grover k=2,3 (separación exponencial)
K_VALUES = [2, 3]                     # Grover principal
N_RANGE_K4 = [4, 5]                   # Grover k=4 puntual: muestra el colapso del oráculo

OUTPUT_DIR = "data"
os.makedirs(OUTPUT_DIR, exist_ok=True)
TIMESTAMP = datetime.now().strftime("%Y%m%d_%H%M")


class CSVWriter:
    """Escritor incremental de CSV por algoritmo, robusto frente a columnas heterogéneas."""

    def __init__(self, algoritmo: str):
        nombre_archivo = f"benchmark_{algoritmo}_{TIMESTAMP}.csv"
        self.path = os.path.join(OUTPUT_DIR, nombre_archivo)
        self.fieldnames: list[str] | None = None

    def append(self, row: dict):
        """Agrega una fila. La primera escritura fija el encabezado y todas las siguientes lo respetan."""
        if self.fieldnames is None:
            self.fieldnames = list(row.keys())
            with open(self.path, "w", newline="") as f:
                writer = csv.DictWriter(f, fieldnames=self.fieldnames)
                writer.writeheader()
                writer.writerow(row)
        else:
            # Si aparece una columna nueva, se añade al esquema y se rescribe el archivo.
            nuevas = [k for k in row.keys() if k not in self.fieldnames]
            if nuevas:
                self.fieldnames = self.fieldnames + nuevas
                self._rewrite_with_new_schema()
            with open(self.path, "a", newline="") as f:
                writer = csv.DictWriter(
                    f, fieldnames=self.fieldnames, extrasaction="ignore"
                )
                writer.writerow(row)

    def _rewrite_with_new_schema(self):
        """Reescribe el archivo cuando aparecen columnas no vistas antes (caso poco frecuente)."""
        with open(self.path, "r", newline="") as f:
            reader = csv.DictReader(f)
            filas = list(reader)
        with open(self.path, "w", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=self.fieldnames, extrasaction="ignore")
            writer.writeheader()
            for fila in filas:
                writer.writerow(fila)


def get_worst_case_bv_secret(n: int) -> str:
    """Peor caso para BV: secreto de puros 1s maximiza las CX."""
    return "1" * n


def get_simon_secret(n: int) -> str:
    """Secreto 2-a-1 estándar para Simon."""
    return "1" * (n - 1) + "0"


def get_hard_grover_expression(n_vars: int, k_val: int, max_intentos: int = 150) -> str:
    """
    Busca una instancia k-SAT satisfacible con pocas soluciones para que la
    amplificación de amplitud de Grover sea efectiva.

    Estrategia adaptativa: cuando k=n cada cláusula sólo excluye una asignación,
    así que se necesitan más cláusulas y un umbral de soluciones más laxo.
    Se va escalando el número de cláusulas y el límite máximo hasta encontrar algo
    razonable. Como último recurso, devuelve la mejor instancia satisfacible vista.
    """
    actual_k = min(k_val, n_vars)

    # Programa progresivo: (multiplicador de cláusulas, límite máximo de soluciones)
    # Cuando k=n cada cláusula filtra muy poco, así que partimos con más cláusulas y subimos.
    if actual_k == n_vars:
        plan = [(4, 2), (6, 3), (8, 5), (12, 8)]
    else:
        plan = [(2, 1), (3, 2), (4, 3), (6, 5)]

    mejor_expr = ""
    mejor_num_soluciones = 2 ** n_vars  # cualquier solución es mejor que ninguna restricción

    for mult, limite in plan:
        m_clauses = max(1, n_vars * mult)
        for _ in range(max_intentos):
            expr = KSATGenerator.generate_random_cnf(n_vars, m_clauses, actual_k)
            valid_sols, _ = KSATSolver.solve_classical(n_vars, expr)
            num = len(valid_sols)
            if 1 <= num <= limite:
                return expr
            # Conservar el mejor candidato satisfacible visto (menor # de soluciones).
            if 1 <= num < mejor_num_soluciones:
                mejor_expr = expr
                mejor_num_soluciones = num

    if mejor_expr:
        # Fallback: instancia satisfacible aunque no esté en el rango ideal.
        return mejor_expr
    raise RuntimeError(
        f"No se encontró ninguna instancia k-SAT satisfacible para n={n_vars}, k={actual_k}"
    )


def run_experiment_loops(
    algo_name: str,
    n_range: list,
    benchmarker_obj,
    get_inputs_func,
    writer: CSVWriter,
):
    """
    Bucle genérico: para cada n y cada topología corre primero el caso ideal
    una sola vez y luego todas las combinaciones (modelo × nivel) de ruido.
    """
    iters_por_n = len(TOPOLOGIES) * (1 + len(NOISE_TYPES) * len(NOISE_LEVELS))
    total_iters = len(n_range) * iters_por_n

    with tqdm(total=total_iters, desc=f"Progreso {algo_name}") as pbar:
        for n in n_range:
            kwargs = get_inputs_func(n)

            for topology in TOPOLOGIES:
                res_ideal = benchmarker_obj.run_experiment(
                    **kwargs,
                    noise_level=0.0,
                    noise_type="ideal",
                    topology=topology,
                )
                writer.append(res_ideal)
                pbar.update(1)

                for n_type in NOISE_TYPES:
                    for n_level in NOISE_LEVELS:
                        res_noisy = benchmarker_obj.run_experiment(
                            **kwargs,
                            noise_level=n_level,
                            noise_type=n_type,
                            topology=topology,
                        )
                        writer.append(res_noisy)
                        pbar.update(1)


if __name__ == "__main__":
    print(f"[{datetime.now().strftime('%H:%M:%S')}] Iniciando benchmarking — timestamp: {TIMESTAMP}")

    if RUN_CONFIG["BV"]:
        writer = CSVWriter("bv")
        bm_bv = BVBenchmarker(shots=SHOTS, repeats=REPEATS)
        def bv_inputs(n): return {"secret": get_worst_case_bv_secret(n)}
        run_experiment_loops("Bernstein-Vazirani", N_RANGE_LINEAR, bm_bv, bv_inputs, writer)

    if RUN_CONFIG["SIMON"]:
        writer = CSVWriter("simon")
        bm_simon = SimonBenchmarker(repeats=REPEATS)
        def simon_inputs(n): return {"secret": get_simon_secret(n)}
        run_experiment_loops("Simon", N_RANGE_EXP, bm_simon, simon_inputs, writer)

    if RUN_CONFIG["GROVER"]:
        writer_g = CSVWriter("grover")

        # Grover principal (k=2 y k=3)
        bm_grover = GroverBenchmarker(shots=SHOTS, repeats=REPEATS)
        for k in K_VALUES:
            def grover_inputs(n, current_k=k):
                expr = get_hard_grover_expression(n, current_k)
                return {
                    "name": f"{current_k}SAT_n{n}",
                    "expression": expr,
                    "num_vars": n,
                }
            valid_n_range = [n for n in N_RANGE_EXP if n >= k]
            run_experiment_loops(
                f"Grover {k}-SAT", valid_n_range, bm_grover, grover_inputs, writer_g
            )

        # Grover k=4 puntual (caso costoso, repeats reducidos)
        bm_grover_k4 = GroverBenchmarker(shots=SHOTS, repeats=GROVER_K4_REPEATS)
        def grover_inputs_k4(n):
            expr = get_hard_grover_expression(n, 4)
            return {
                "name": f"4SAT_n{n}",
                "expression": expr,
                "num_vars": n,
            }
        run_experiment_loops(
            "Grover 4-SAT", N_RANGE_K4, bm_grover_k4, grover_inputs_k4, writer_g
        )

    if RUN_CONFIG["QPE"]:
        writer = CSVWriter("qpe")
        bm_qpe = QPEBenchmarker(shots=SHOTS, repeats=REPEATS)
        # Fase fija no-binaria (genera phase leakage); se varía la precisión (qubits de conteo).
        def qpe_inputs(n): return {"theta": 0.333, "n_qubits": n}
        run_experiment_loops("QPE", N_RANGE_LINEAR, bm_qpe, qpe_inputs, writer)

    print(f"\n[{datetime.now().strftime('%H:%M:%S')}] Datos recolectados en: {OUTPUT_DIR}/benchmark_*_{TIMESTAMP}.csv")
