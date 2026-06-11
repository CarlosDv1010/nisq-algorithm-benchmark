import itertools
from typing import Dict, Any, Tuple, List

import numpy as np
from qiskit import QuantumCircuit, transpile
from qiskit.circuit.library import PhaseOracle, GroverOperator
from qiskit_aer import AerSimulator

from src.utils.noise_factory import get_nisq_model, get_hardware_specs
from src.utils.metrics import calculate_statistics, calculate_circuit_duration


class KSATSolver:
    """Lógica clásica y cuántica para resolver k-SAT con el algoritmo de Grover."""

    @staticmethod
    def solve_classical(num_vars: int, expresion: str) -> Tuple[List[str], int]:
        """Fuerza bruta sobre las 2^n asignaciones booleanas. Retorna soluciones y evaluaciones."""
        soluciones = []
        evaluaciones = 0

        for seq in itertools.product([False, True], repeat=num_vars):
            evaluaciones += 1
            env = {f"v{i}": val for i, val in enumerate(seq)}
            py_expr = expresion.replace('|', 'or').replace('&', 'and').replace('~', 'not ')

            try:
                if eval(py_expr, {}, env):
                    bin_sol = "".join(
                        ['1' if env[f"v{i}"] else '0' for i in range(num_vars - 1, -1, -1)]
                    )
                    soluciones.append(bin_sol)
            except Exception as e:
                raise ValueError(f"Error evaluando la expresión '{expresion}': {e}")

        return soluciones, evaluaciones

    @staticmethod
    def calculate_optimal_iterations(num_vars: int, num_soluciones: int) -> int:
        """Iteraciones óptimas de Grover: T ≈ (π/4)·√(N/M) con N = 2^n y M soluciones."""
        if num_soluciones == 0:
            return 0
        N = 2 ** num_vars
        T = (np.pi / 4) * np.sqrt(N / num_soluciones)
        return int(np.floor(T))

    @staticmethod
    def get_quantum_solutions(expresion: str, num_vars: int) -> List[str]:
        """
        Devuelve las soluciones EN LA CONVENCIÓN INTERNA QUE QISKIT USA EN PhaseOracle.

        PhaseOracle no asigna `v_i` al qubit `i`: las variables se mapean a qubits
        en el orden en que aparecen en la expresión. Como las cláusulas se generan
        aleatoriamente, ese orden casi nunca coincide con el orden numérico, así
        que comparar los counts contra los strings de `solve_classical` produce
        falsos negativos. `evaluate_bitstring` respeta el mapeo interno del oráculo
        y devuelve la asignación verdadera por estado.
        """
        oraculo = PhaseOracle(expresion)
        soluciones = []
        for i in range(2 ** num_vars):
            bitstring = format(i, f"0{num_vars}b")
            if oraculo.evaluate_bitstring(bitstring):
                soluciones.append(bitstring)
        return soluciones

    @staticmethod
    def build_quantum_circuit(expresion: str, num_vars: int, iteraciones: int) -> QuantumCircuit:
        """Construye el oráculo de fase y el operador de Grover a partir de una fórmula CNF."""
        oraculo = PhaseOracle(expresion)
        grover_op = GroverOperator(oraculo)

        qc = QuantumCircuit(num_vars, num_vars)
        qc.h(range(num_vars))

        for _ in range(iteraciones):
            qc.compose(grover_op, inplace=True)

        qc.measure(range(num_vars), range(num_vars))
        return qc


class GroverBenchmarker:
    """Ejecuta experimentos de Grover sobre instancias k-SAT y agrega las métricas del circuito."""

    def __init__(self, shots: int = 1024, repeats: int = 100):
        self.shots = shots
        self.repeats = repeats

    def run_experiment(
        self,
        name: str,
        expression: str,
        num_vars: int,
        noise_level: float = 0.0,
        noise_type: str = 'ideal',
        topology: str = 'ideal',
    ) -> Dict[str, Any]:
        """Corre el experimento completo y devuelve las métricas en un diccionario."""
        soluciones, evaluaciones_clasicas = KSATSolver.solve_classical(num_vars, expression)
        num_soluciones = len(soluciones)
        iteraciones = KSATSolver.calculate_optimal_iterations(num_vars, num_soluciones)

        # Soluciones en el orden de qubits que usa Qiskit internamente. Imprescindible
        # para sumar los counts correctamente (ver get_quantum_solutions).
        soluciones_quantum = KSATSolver.get_quantum_solutions(expression, num_vars)

        qc = KSATSolver.build_quantum_circuit(expression, num_vars, iteraciones)
        # PhaseOracle y GroverOperator requieren descomposición previa a compuertas base.
        qc = transpile(qc, basis_gates=['u', 'cx', 'id'], optimization_level=1)

        noise_model = get_nisq_model(noise_type, noise_level)
        sim = AerSimulator(noise_model=noise_model)

        specs = get_hardware_specs(topology)
        tqc = transpile(
            qc,
            coupling_map=specs["coupling_map"],
            basis_gates=specs["basis_gates"],
            optimization_level=3,
        )
        duration_ns = calculate_circuit_duration(tqc, specs["instruction_durations"])

        profundidad = tqc.depth()
        cx_gates = tqc.count_ops().get('cx', 0)

        fidelidades = []
        for _ in range(self.repeats):
            job = sim.run(tqc, shots=self.shots)
            counts = job.result().get_counts()

            # Se suman las mediciones de todas las asignaciones válidas (amplificación de amplitud).
            shots_exitosos = sum(counts.get(sol, 0) for sol in soluciones_quantum)
            fidelidades.append((shots_exitosos / self.shots) * 100)

        stats = calculate_statistics(fidelidades, confidence=0.95)

        resultado = {
            'algoritmo': 'Grover k-SAT',
            'instancia': name,
            'n_bits': num_vars,
            'k_clausulas': expression.count('&') + 1 if expression else 0,
            'soluciones_esperadas': num_soluciones,
            'noise_level': noise_level,
            'noise_type': noise_type,
            'topology': topology,
            'classic_queries': evaluaciones_clasicas,
            'quantum_queries': iteraciones,
            'transpiled_depth': profundidad,
            'cx_gates': cx_gates,
            'duration_ns': duration_ns,
        }
        resultado.update(stats)
        return resultado
