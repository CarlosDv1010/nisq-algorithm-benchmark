from typing import Dict, Any

from qiskit import QuantumCircuit, transpile
from qiskit_aer import AerSimulator

from src.utils.noise_factory import get_nisq_model, get_hardware_specs
from src.utils.metrics import calculate_statistics, calculate_circuit_duration


class BernsteinVaziraniSolver:
    """Lógica clásica y cuántica del algoritmo de Bernstein-Vazirani."""

    @staticmethod
    def build_classical_oracle(secret: str):
        """Oráculo clásico: producto punto bit a bit módulo 2."""
        def oracle(entrada: str) -> str:
            return str(sum(int(q) * int(s) for q, s in zip(entrada, secret)) % 2)
        return oracle

    @staticmethod
    def solve_classical(secret: str) -> int:
        """Recupera el secreto consultando bit por bit. Retorna el número de consultas (O(N))."""
        n = len(secret)
        oracle = BernsteinVaziraniSolver.build_classical_oracle(secret)
        consultas = 0

        for i in range(n):
            entrada = ['0'] * n
            entrada[i] = '1'
            oracle("".join(entrada))
            consultas += 1

        return consultas

    @staticmethod
    def build_quantum_circuit(secret: str) -> QuantumCircuit:
        """Construye el circuito de Bernstein-Vazirani para el secreto dado."""
        n = len(secret)
        qc = QuantumCircuit(n + 1, n)

        qc.h(range(n))
        qc.x(n)
        qc.h(n)
        qc.barrier()

        # Qiskit indexa en little endian, por eso se recorre el secreto al revés
        for i, bit in enumerate(secret[::-1]):
            if bit == '1':
                qc.cx(i, n)

        qc.barrier()
        qc.h(range(n))
        qc.measure(range(n), range(n))

        return qc


class BVBenchmarker:
    """Ejecuta experimentos de Bernstein-Vazirani y agrega las métricas del circuito."""

    def __init__(self, shots: int = 1000, repeats: int = 100):
        self.shots = shots
        self.repeats = repeats

    def run_experiment(
        self,
        secret: str,
        noise_level: float = 0.0,
        noise_type: str = 'ideal',
        topology: str = 'ideal',
    ) -> Dict[str, Any]:
        """Corre el experimento completo y devuelve las métricas en un diccionario."""
        n = len(secret)

        consultas_clasicas = BernsteinVaziraniSolver.solve_classical(secret)
        qc = BernsteinVaziraniSolver.build_quantum_circuit(secret)
        noise_model = get_nisq_model(noise_type, noise_level)

        # Se usa AerSimulator con shots en todos los casos (ideal y ruidoso) para que
        # la estadística (media, IC95) quede homogénea entre algoritmos y escenarios.
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
            prob_exito = counts.get(secret, 0) / self.shots
            fidelidades.append(prob_exito * 100)

        stats = calculate_statistics(fidelidades, confidence=0.95)

        resultado = {
            'algoritmo': 'Bernstein-Vazirani',
            'n_bits': n,
            'secret': secret,
            'noise_level': noise_level,
            'noise_type': noise_type,
            'topology': topology,
            'classic_queries': consultas_clasicas,
            'quantum_queries': 1,
            'transpiled_depth': profundidad,
            'cx_gates': cx_gates,
            'duration_ns': duration_ns,
        }
        resultado.update(stats)
        return resultado
