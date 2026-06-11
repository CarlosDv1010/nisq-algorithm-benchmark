from qiskit_aer.noise import (
    NoiseModel,
    depolarizing_error,
    ReadoutError,
    thermal_relaxation_error,
)
from qiskit_ibm_runtime.fake_provider import FakeBrisbane
from qiskit.providers.fake_provider import GenericBackendV2


def get_nisq_model(noise_type: str = 'depolarizing', noise_level: float = 0.0) -> NoiseModel:
    """
    Fabrica modelos de ruido que emulan los principales efectos físicos de la era NISQ.

    Args:
        noise_type: 'ideal', 'readout_only', 'depolarizing' o 'thermal'.
        noise_level: Tasa base de error (ej. 0.05 para 5%). En el modelo térmico
            escala la degradación de T1/T2.
    """
    if noise_type == 'ideal' or noise_level <= 0.0:
        return None

    noise_model = NoiseModel()
    basis_1q = ['id', 'rz', 'sx', 'x', 'h', 'u1', 'u2', 'u3']
    basis_2q = ['cx']

    if noise_type == 'readout_only':
        # Aísla el error a la fase de medición; útil para evaluar la fragilidad de Simon.
        p_ro = min(noise_level, 0.5)
        ro_error = ReadoutError([[1 - p_ro, p_ro], [p_ro, 1 - p_ro]])
        noise_model.add_all_qubit_readout_error(ro_error)

    elif noise_type == 'depolarizing':
        # Modelo estándar: errores en compuertas y medición.
        # Las CX se asumen 10× más ruidosas que las compuertas de 1 qubit.
        p_1q = noise_level / 10.0
        p_2q = noise_level

        noise_model.add_all_qubit_quantum_error(depolarizing_error(p_1q, 1), basis_1q)
        noise_model.add_all_qubit_quantum_error(depolarizing_error(p_2q, 2), basis_2q)

        p_ro = min(noise_level * 1.5, 0.5)
        noise_model.add_all_qubit_readout_error(
            ReadoutError([[1 - p_ro, p_ro], [p_ro, 1 - p_ro]])
        )

    elif noise_type == 'thermal':
        # Tiempos base inspirados en chips IBM reales: T1 ~ 100 µs, T2 ~ 70 µs.
        # T2 < T1 refleja el desfase puro adicional al decaimiento de amplitud.
        # El factor de escala (1 - noise_level) modela el envejecimiento del hardware.
        escala = 1.0 - min(noise_level, 0.99)
        t1 = 100_000 * escala
        t2 = min(70_000 * escala, 2 * t1)  # se respeta la cota física T2 ≤ 2·T1

        tiempo_1q = 50    # 50 ns por compuerta de 1 qubit
        tiempo_2q = 300   # 300 ns por compuerta CX

        error_1q = thermal_relaxation_error(t1, t2, tiempo_1q)
        error_2q = thermal_relaxation_error(t1, t2, tiempo_2q).expand(
            thermal_relaxation_error(t1, t2, tiempo_2q)
        )

        noise_model.add_all_qubit_quantum_error(error_1q, basis_1q)
        noise_model.add_all_qubit_quantum_error(error_2q, basis_2q)

        p_ro = min(noise_level, 0.5)
        noise_model.add_all_qubit_readout_error(
            ReadoutError([[1 - p_ro, p_ro], [p_ro, 1 - p_ro]])
        )

    else:
        raise ValueError(f"Tipo de ruido no soportado: {noise_type}")

    return noise_model


def get_hardware_specs(topology: str = "ideal"):
    """Devuelve la configuración de hardware (coupling map, basis gates, duraciones) por topología."""
    if topology == "ideal":
        return {"coupling_map": None, "basis_gates": None, "instruction_durations": None}

    if topology == "heavy-hex":
        # FakeBrisbane aproxima al chip real de 127 qubits de IBM.
        backend = FakeBrisbane()
        return {
            "coupling_map": backend.coupling_map,
            "basis_gates": backend.operation_names,
            "instruction_durations": backend.instruction_durations,
        }

    if topology == "line":
        # Topología lineal de 20 qubits: peor caso de enrutamiento, fuerza muchos SWAPs.
        backend = GenericBackendV2(
            num_qubits=20,
            coupling_map=[[i, i + 1] for i in range(19)],
        )
        return {
            "coupling_map": backend.coupling_map,
            "basis_gates": backend.operation_names,
            "instruction_durations": backend.instruction_durations,
        }

    return {"coupling_map": None, "basis_gates": None, "instruction_durations": None}
