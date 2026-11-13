"""La partida: veinte turnos, diez planillas por jugador, y gana el que suma más.

Los dos jugadores llenan las diez categorías. Los turnos se alternan y el
primero en empezar se alterna entre partidas, porque arrancar da una ventaja
chica pero real: el que va primero elige categorías con la planilla del rival
todavía vacía.

La generala servida corta la partida en el acto. Es la única forma de ganar
sin llenar la planilla.
"""

from app.modules.games.generala.dados import CATEGORIAS, es_generala
from app.modules.games.generala.fairness import FlujoDeDados
from app.modules.games.generala.turno import Turno

__all__ = ["JUGADORES", "Partida"]

JUGADORES = 2


class Partida:
    def __init__(
        self,
        server_seed: str,
        client_seed: str,
        nonce: int,
        empieza: int = 0,
    ):
        self.server_seed = server_seed
        self.client_seed = client_seed
        self.nonce = nonce
        self.empieza = empieza

        # Un solo flujo para toda la partida: los dados salen en el orden en
        # que se tiran, así rehacer las acciones rehace la partida entera.
        self.flujo = FlujoDeDados(server_seed, client_seed, nonce)

        self.planillas = [
            {categoria: None for categoria in CATEGORIAS} for _ in range(JUGADORES)
        ]
        self.turnos_jugados = 0
        self.en_turno = empieza
        self.turno = None

        self.terminada = False
        self.ganador = None
        self.generala_servida_de = None

        self._abrir_turno()

    # ------------------------------ el recorrido ------------------------------

    def _abrir_turno(self) -> None:
        if self.terminada:
            return

        disponibles = self.disponibles(self.en_turno)
        if not disponibles:
            self._cerrar_partida()
            return

        self.turno = Turno(self.flujo, disponibles)

        if es_generala(self.turno.dados):
            self._resolver_generala_servida()

    def _resolver_generala_servida(self) -> None:
        """Los cinco iguales en la primera tirada. Qué pasa depende de la fila.

        - Si la generala está libre, gana la partida en el acto.
        - Si ya está anotada con puntos, es doble generala y también gana.
        - Si está tachada con cero, no hay premio: el jugador la resignó y el
          turno sigue como cualquier otro. Sin este caso el motor rompía,
          porque intentaba anotar en una fila ya usada.
        """
        jugador = self.en_turno
        anotada = self.planillas[jugador]["generala"]

        if anotada == 0:
            return

        if anotada is None:
            self.turno.anotar("generala")
            self.planillas[jugador]["generala"] = self.turno.puntos

        self.generala_servida_de = jugador
        self.ganador = jugador
        self.terminada = True

    def cerrar_turno(self) -> None:
        """Pasa lo anotado a la planilla y le da el turno al otro."""
        if self.terminada:
            return

        if self.turno is None or not self.turno.terminado:
            raise RuntimeError("El turno todavía no terminó")

        self.planillas[self.en_turno][self.turno.categoria] = self.turno.puntos
        self.turnos_jugados += 1
        self.en_turno = 1 - self.en_turno
        self._abrir_turno()

    def _cerrar_partida(self) -> None:
        self.terminada = True
        self.turno = None

        uno, otro = self.total(0), self.total(1)
        # El empate existe y hay que nombrarlo: con plata de por medio, no
        # decidirlo sería quedarse con la apuesta de los dos.
        self.ganador = None if uno == otro else (0 if uno > otro else 1)

    # ------------------------------ la planilla ------------------------------

    def disponibles(self, jugador: int) -> list:
        return [
            categoria
            for categoria, puntos in self.planillas[jugador].items()
            if puntos is None
        ]

    def total(self, jugador: int) -> int:
        return sum(
            puntos for puntos in self.planillas[jugador].values() if puntos is not None
        )

    # ------------------------------ vista ------------------------------

    def estado(self, para: int = None) -> dict:
        estado = {
            "planillas": [dict(planilla) for planilla in self.planillas],
            "totales": [self.total(0), self.total(1)],
            "en_turno": self.en_turno,
            "turnos_jugados": self.turnos_jugados,
            "empieza": self.empieza,
            "terminada": self.terminada,
            "ganador": self.ganador,
            "generala_servida_de": self.generala_servida_de,
        }

        if self.turno is not None:
            estado["turno"] = self.turno.estado()
            # Los dados están a la vista de los dos: en la generala no hay
            # información oculta, a diferencia del truco.
            estado["turno"]["es_mio"] = para is None or para == self.en_turno

        return estado
