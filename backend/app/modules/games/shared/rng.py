"""Fuente de aleatoriedad de los juegos.

El módulo `random` usa Mersenne Twister, que no es criptográfico: observando
suficientes resultados se reconstruye su estado interno y se predicen los
siguientes. En un casino los resultados son públicos por diseño (el número que
salió, el crash point de cada ronda), así que todo lo que decide plata tiene que
salir del CSPRNG del sistema.
"""

import secrets

system_random = secrets.SystemRandom()


def choice(secuencia):
    """Elige un elemento al azar, sin sesgo de módulo."""
    return system_random.choice(secuencia)


def shuffle(items) -> None:
    """Mezcla la lista in place (Fisher-Yates sobre el CSPRNG)."""
    system_random.shuffle(items)


def uniform(minimo: float, maximo: float) -> float:
    """Float al azar en el rango. Se usa para el jitter visual de Plinko."""
    return system_random.uniform(minimo, maximo)
