"""Un turno de generala: hasta tres tiradas y después hay que anotar.

El jugador tira los cinco dados, y puede volver a tirar los que quiera dos
veces más. Puede anotar en cualquier momento, no está obligado a usar las tres
tiradas; anotar en la primera es lo que hace que una figura cuente como
servida.

Anotar es obligatorio: si ninguna categoría disponible da puntos, se tacha una
con cero. Eso es parte del juego y es donde se decide la partida más seguido
que en los dados, porque hay que elegir qué sacrificar.
"""

from app.modules.games.generala.dados import (
    CATEGORIAS,
    DADOS,
    categoria_valida,
    puntaje,
    puntajes_posibles,
)

__all__ = ["TIRADAS_POR_TURNO", "Turno", "aplicar_accion"]

TIRADAS_POR_TURNO = 3


class Turno:
    def __init__(self, flujo, disponibles):
        """`flujo` reparte los dados; `disponibles` son las categorías sin usar."""
        if not disponibles:
            raise ValueError("No quedan categorías para anotar")

        self.flujo = flujo
        self.disponibles = [c for c in CATEGORIAS if c in set(disponibles)]

        self.dados = flujo.tirar(DADOS)
        self.tirada = 1
        # Las tiradas que se fueron dando, para poder mostrar y verificar.
        self.historial = [list(self.dados)]

        self.terminado = False
        self.categoria = None
        self.puntos = 0

    # ------------------------------ estado ------------------------------

    @property
    def servida(self) -> bool:
        """Todavía no volvió a tirar nada, así que lo que salga es servido."""
        return self.tirada == 1

    @property
    def puede_tirar(self) -> bool:
        return not self.terminado and self.tirada < TIRADAS_POR_TURNO

    def puntajes(self) -> dict:
        """Lo que daría cada categoría disponible si anotara ahora."""
        todos = puntajes_posibles(self.dados, servida=self.servida)
        return {
            categoria: puntos
            for categoria, puntos in todos.items()
            if categoria in self.disponibles
        }

    def acciones(self) -> list:
        if self.terminado:
            return []

        acciones = ["anotar:%s" % categoria for categoria in self.disponibles]
        if self.puede_tirar:
            acciones.insert(0, "tirar")

        return acciones

    # ------------------------------ jugar ------------------------------

    def tirar(self, indices) -> list:
        """Vuelve a tirar los dados de esas posiciones."""
        if self.terminado:
            raise ValueError("El turno ya terminó")

        if not self.puede_tirar:
            raise ValueError("Ya usaste las %s tiradas" % TIRADAS_POR_TURNO)

        indices = sorted(set(indices))
        if not indices:
            raise ValueError("Elegí al menos un dado para volver a tirar")

        if any(not 0 <= indice < DADOS for indice in indices):
            raise ValueError("Los dados van del 0 al %s" % (DADOS - 1))

        nuevos = self.flujo.tirar(len(indices))
        for posicion, indice in enumerate(indices):
            self.dados[indice] = nuevos[posicion]

        self.tirada += 1
        self.historial.append(list(self.dados))
        return list(self.dados)

    def anotar(self, categoria: str) -> int:
        """Cierra el turno anotando en esa categoría. Puede ser un cero."""
        if self.terminado:
            raise ValueError("El turno ya terminó")

        if not categoria_valida(categoria):
            raise ValueError("No existe la categoría %r" % categoria)

        if categoria not in self.disponibles:
            raise ValueError("Esa categoría ya está usada")

        self.categoria = categoria
        self.puntos = puntaje(categoria, self.dados, servida=self.servida)
        self.terminado = True
        return self.puntos

    # ------------------------------ vista ------------------------------

    def estado(self) -> dict:
        return {
            "dados": list(self.dados),
            "tirada": self.tirada,
            "tiradas_por_turno": TIRADAS_POR_TURNO,
            "puede_tirar": self.puede_tirar,
            "servida": self.servida,
            "puntajes": self.puntajes(),
            "acciones": self.acciones(),
            "terminado": self.terminado,
            "categoria": self.categoria,
            "puntos": self.puntos,
            "historial": [list(tirada) for tirada in self.historial],
        }


def aplicar_accion(turno: Turno, accion: str):
    """Ejecuta una acción del registro. Es lo que permite rehacer la partida.

    Las acciones son texto porque se guardan tal cual y se vuelven a aplicar:
    "tirar:0,2,4" vuelve a tirar esos dados, "anotar:escalera" cierra el turno.
    """
    if accion.startswith("tirar:"):
        crudos = accion.split(":", 1)[1]
        indices = [int(parte) for parte in crudos.split(",") if parte != ""]
        return turno.tirar(indices)

    if accion.startswith("anotar:"):
        return turno.anotar(accion.split(":", 1)[1])

    raise ValueError("Acción desconocida: %r" % accion)
