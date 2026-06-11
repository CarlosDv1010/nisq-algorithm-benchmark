from typing import Dict, Any

import numpy as np
from qiskit import QuantumCircuit, transpile
from qiskit.circuit.library import QFT
from qiskit_aer import AerSimulator

from src.utils.noise_factory import get_nisq_model, get_hardware_specs
from src.utils.metrics import calculate_statistics, calculate_circuit_duration


class QPESolver:
    """Estimación de Fase Cuántica sobre un operador U con U|ψ⟩ = exp(2π i θ)|ψ⟩."""

    @staticmethod
    def solve_classical(theta: float, num_counting_qubits: int) -> float:
        """Mejor aproximación binaria de θ dada la resolución disponible."""
        discreto = round(theta * (2**num_counting_qubits))
        return discreto / (2**num_counting_qubits)

    @staticmethod
    def build_quantum_circuit(theta: float, num_counting_qubits: int) -> QuantumCircuit:
        """Construye el circuito de QPE para una fase dada usando un PhaseGate controlado."""
        total_qubits = num_counting_qubits + 1
        qc = QuantumCircuit(total_qubits, num_counting_qubits)
        qc.x(num_counting_qubits)

        qc.h(range(num_counting_qubits))

        angulo = 2 * np.pi * theta
        for counting_qubit in range(num_counting_qubits):
            repeticiones = 2 ** counting_qubit
            for _ in range(repeticiones):
                qc.cp(angulo, counting_qubit, num_counting_qubits)

        iqft = QFT(num_counting_qubits, inverse=True).to_gate()
        iqft.label = "IQFT†"
        qc.append(iqft, range(num_counting_qubits))

        qc.measure(range(num_counting_qubits), range(num_counting_qubits))
        return qc

    @staticmethod
    def bitstring_to_phase(bitstring: str) -> float:
        """Convierte una cadena binaria (ej. '101') en la fase decimal que representa."""
        n = len(bitstring)
        return int(bitstring, 2) / (2**n)


class QPEBenchmarker:
    """Ejecuta experimentos de QPE y agrega las métricas del circuito."""

    def __init__(self, shots: int = 1024, repeats: int = 100):
        self.shots = shots
        self.repeats = repeats

    def run_experiment(
        self,
        theta: float,
        n_qubits: int,
        noise_level: float = 0.0,
        noise_type: str = 'ideal',
        topology: str = 'ideal',
    ) -> Dict[str, Any]:
        """Corre el experimento completo y devuelve las métricas en un diccionario."""
        qc = QPESolver.build_quantum_circuit(theta, n_qubits)

        noise_model = get_nisq_model(noise_type, noise_level)
        sim = AerSimulator(noise_model=noise_model)

        # La QFT no se descompone directamente en compuertas base, se hace un unrolling previo.
        qc = transpile(qc, basis_gates=['u', 'cx', 'id'], optimization_level=1)

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

        fase_objetivo = QPESolver.solve_classical(theta, n_qubits)
        esperado_bin = format(int(fase_objetivo * (2**n_qubits)), f'0{n_qubits}b')

        fidelidades = []
        for _ in range(self.repeats):
            job = sim.run(tqc, shots=self.shots)
            counts = job.result().get_counts()
            shots_exitosos = counts.get(esperado_bin, 0)
            fidelidades.append((shots_exitosos / self.shots) * 100)

        stats = calculate_statistics(fidelidades)

        resultado = {
            'algoritmo': 'QPE',
            'n_bits': n_qubits,
            'theta_original': theta,
            'theta_discretizado': fase_objetivo,
            'noise_level': noise_level,
            'noise_type': noise_type,
            'topology': topology,
            'transpiled_depth': profundidad,
            'cx_gates': cx_gates,
            'total_gates': sum(tqc.count_ops().values()),
            'duration_ns': duration_ns,
        }
        resultado.update(stats)
        return resultado
