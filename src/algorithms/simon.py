from typing import Dict, Any, List, Optional

from qiskit import QuantumCircuit, transpile
from qiskit_aer import AerSimulator

from src.utils.noise_factory import get_nisq_model, get_hardware_specs
from src.utils.metrics import calculate_statistics, calculate_circuit_duration


class SimonSolver:
    """Lógica clásica y cuántica del algoritmo de Simon."""

    @staticmethod
    def solve_classical(secreto: str) -> int:
        """Busca una colisión f(x)=f(x⊕s) por fuerza bruta y devuelve el número de consultas."""
        n = len(secreto)
        historial = {}
        consultas = 0

        for i in range(2**n):
            consultas += 1
            x = format(i, f'0{n}b')
            val_x = int(x, 2)
            val_s = int(secreto, 2)

            # Simulación de la colisión: la función cumple f(x) = f(x⊕s)
            clave = min(val_x, val_x ^ val_s)

            if clave in historial:
                return consultas
            historial[clave] = i

        return consultas

    @staticmethod
    def build_quantum_circuit(secreto: str) -> QuantumCircuit:
        """Construye el circuito de Simon para el secreto dado."""
        n = len(secreto)
        qc = QuantumCircuit(2 * n, n)

        qc.h(range(n))
        qc.barrier()

        # Oráculo: copia x al segundo registro y aplica la relación del secreto
        for i in range(n):
            qc.cx(i, i + n)

        primer_uno = secreto.find('1')
        if primer_uno != -1:
            for i, bit in enumerate(secreto):
                if bit == '1':
                    qc.cx(primer_uno, i + n)

        qc.barrier()
        qc.h(range(n))
        qc.measure(range(n), range(n))

        return qc

    @staticmethod
    def solve_gf2_system(z_vectors: List[List[int]], n: int) -> List[str]:
        """Devuelve los candidatos s ≠ 0 que satisfacen z·s = 0 (mod 2) para todos los z medidos."""
        candidatos = []
        for i in range(1, 2**n):
            candidato = format(i, f'0{n}b')
            cvec = [int(b) for b in candidato]

            valido = True
            for z in z_vectors:
                if sum(a * b for a, b in zip(z, cvec)) % 2 != 0:
                    valido = False
                    break

            if valido:
                candidatos.append(candidato)

        return candidatos


class SimonBenchmarker:
    """Ejecuta experimentos de Simon y agrega las métricas del circuito."""

    def __init__(self, repeats: int = 100):
        # Simon requiere muestreo continuo hasta encontrar N-1 vectores independientes,
        # por eso se usa un número dinámico de shots por intento en lugar de uno fijo.
        self.repeats = repeats

    def _execute_single_run(
        self, secret: str, tqc: QuantumCircuit, sim: AerSimulator
    ) -> Optional[str]:
        """Muestrea el circuito y resuelve el sistema GF(2) hasta obtener el secreto o fallar."""
        n = len(secret)
        # Cota empírica: ~6N shots bastan para obtener N-1 vectores linealmente independientes.
        shots_limit = 6 * n

        job = sim.run(tqc, shots=shots_limit, memory=True)
        mediciones = job.result().get_memory()

        z_vectors = []

        for z_str in mediciones:
            z = [int(b) for b in z_str[::-1]]
            if sum(z) > 0 and z not in z_vectors:
                z_vectors.append(z)

                candidatos = SimonSolver.solve_gf2_system(z_vectors, n)

                if len(candidatos) == 1:
                    return candidatos[0]
                # Con ruido los vectores pueden ser incompatibles y dejar el sistema sin solución.
                if len(candidatos) == 0:
                    return None

        return None

    def run_experiment(
        self,
        secret: str,
        noise_level: float = 0.0,
        noise_type: str = 'ideal',
        topology: str = 'ideal',
    ) -> Dict[str, Any]:
        """Corre el experimento completo y devuelve las métricas en un diccionario."""
        n = len(secret)

        consultas_clasicas = SimonSolver.solve_classical(secret)
        qc = SimonSolver.build_quantum_circuit(secret)
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
            resultado_final = self._execute_single_run(secret, tqc, sim)
            exito = 100.0 if resultado_final == secret else 0.0
            fidelidades.append(exito)

        stats = calculate_statistics(fidelidades, confidence=0.95)

        resultado = {
            'algoritmo': 'Simon',
            'n_bits': n,
            'secret': secret,
            'noise_level': noise_level,
            'noise_type': noise_type,
            'topology': topology,
            'classic_queries': consultas_clasicas,
            'quantum_queries': n + 2,
            'transpiled_depth': profundidad,
            'cx_gates': cx_gates,
            'duration_ns': duration_ns,
        }
        resultado.update(stats)
        return resultado
