import random


class KSATGenerator:
    """Generador sencillo de fórmulas CNF aleatorias para instancias de k-SAT."""

    @staticmethod
    def generate_random_cnf(num_vars: int, num_clauses: int, k: int = 3) -> str:
        if k > num_vars:
            raise ValueError("k no puede ser mayor que el número de variables.")

        variables = [f"v{i}" for i in range(num_vars)]
        clausulas = []

        for _ in range(num_clauses):
            elegidas = random.sample(variables, k)
            literales = [
                f"~{var}" if random.choice([True, False]) else var
                for var in elegidas
            ]
            clausulas.append("(" + " | ".join(literales) + ")")

        return " & ".join(clausulas)
