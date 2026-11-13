"""Los dados y el puntaje de la generala.

Cinco dados, diez categorías, cada una se llena una sola vez. Las reglas de la
generala cambian de mesa en mesa, así que acá quedan fijadas las que se juegan,
con el criterio de tomar la versión más difundida en Argentina:

- Números (1 al 6): suma de los dados de ese número. Tres cuatros son 12.
- Escalera: 1-2-3-4-5 o 2-3-4-5-6. La "escalera con el as arriba"
  (3-4-5-6-1), que algunos aceptan, acá no vale.
- Full: tres iguales más dos iguales de otro número. Cinco iguales no es full.
- Póker: cuatro iguales. Cinco iguales también cuenta, porque contienen cuatro.
- Generala: los cinco iguales.

Servida y armada
----------------
Servida es sacarla en la primera tirada del turno, sin volver a tirar ningún
dado. Paga más porque es más difícil: no hay segunda oportunidad.

    categoría   armada   servida
    escalera      20       25
    full          30       35
    póker         40       45
    generala      50       60

La generala servida gana la partida en el acto. Es regla de la casa en casi
todas las mesas y está acá por eso, no por conveniencia: es simétrica, le puede
tocar a cualquiera de los dos.
"""

from collections import Counter

__all__ = [
    "CATEGORIAS",
    "CATEGORIAS_DE_FIGURA",
    "CATEGORIAS_NUMERICAS",
    "DADOS",
    "ESCALERAS",
    "PUNTAJE_ARMADA",
    "PUNTAJE_SERVIDA",
    "categoria_valida",
    "es_generala",
    "puntaje",
    "puntajes_posibles",
]

DADOS = 5
CARAS = 6

CATEGORIAS_NUMERICAS = ("1", "2", "3", "4", "5", "6")
CATEGORIAS_DE_FIGURA = ("escalera", "full", "poker", "generala")
CATEGORIAS = CATEGORIAS_NUMERICAS + CATEGORIAS_DE_FIGURA

ESCALERAS = (
    (1, 2, 3, 4, 5),
    (2, 3, 4, 5, 6),
)

PUNTAJE_ARMADA = {"escalera": 20, "full": 30, "poker": 40, "generala": 50}
PUNTAJE_SERVIDA = {"escalera": 25, "full": 35, "poker": 45, "generala": 60}


def categoria_valida(categoria: str) -> bool:
    return categoria in CATEGORIAS


def _es_escalera(dados) -> bool:
    return tuple(sorted(dados)) in ESCALERAS


def _es_full(dados) -> bool:
    """Tres y dos de números distintos. Cinco iguales no."""
    return sorted(Counter(dados).values()) == [2, 3]


def _es_poker(dados) -> bool:
    """Cuatro iguales. Los cinco iguales contienen cuatro, así que valen."""
    return max(Counter(dados).values()) >= 4


def es_generala(dados) -> bool:
    return len(set(dados)) == 1 and len(dados) == DADOS


_FIGURAS = {
    "escalera": _es_escalera,
    "full": _es_full,
    "poker": _es_poker,
    "generala": es_generala,
}


def puntaje(categoria: str, dados, servida: bool = False) -> int:
    """Lo que suma anotar estos dados en esa categoría. Cero si no la cumple."""
    if not categoria_valida(categoria):
        raise ValueError("No existe la categoría %r" % categoria)

    if len(dados) != DADOS:
        raise ValueError("La generala se juega con %s dados" % DADOS)

    if categoria in CATEGORIAS_NUMERICAS:
        cara = int(categoria)
        # Los números no tienen premio por servida: sumar cuatro cincos en la
        # primera no es más difícil que sumarlos en la tercera, es el mismo
        # resultado, así que pagarlos distinto sería arbitrario.
        return cara * sum(1 for dado in dados if dado == cara)

    if not _FIGURAS[categoria](dados):
        return 0

    tabla = PUNTAJE_SERVIDA if servida else PUNTAJE_ARMADA
    return tabla[categoria]


def puntajes_posibles(dados, servida: bool = False) -> dict:
    """Lo que daría cada categoría con estos dados. Para la planilla y el bot."""
    return {
        categoria: puntaje(categoria, dados, servida) for categoria in CATEGORIAS
    }
