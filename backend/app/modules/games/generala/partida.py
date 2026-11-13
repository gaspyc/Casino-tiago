"""La partida: veinte turnos, diez planillas por jugador, y gana el que suma más.

Los dos jugadores llenan las diez categorías. Los turnos se alternan y el
primero en empezar se alterna entre partidas, porque arrancar da una ventaja
chica pero real: el que va primero elige categorías con la planilla del rival
todavía vacía.

La generala servida corta la partida en el acto. Es la única forma de ganar
sin llenar la planilla.
"""

from app.modules.games.generala.dados import (
    CATEGORIAS,
    PUNTAJE_SERVIDA,
    es_generala,
)
from app.modules.games.generala.fairness import FlujoDeDados
from app.modules.games.generala.turno import Turno, aplicar_accion

__all__ = ["JUGADORES", "Partida", "reconstruir_desde"]

JUGADORES = 2


class Partida:
    def __init__(
        self,
        server_seed: str,
        client_seed: str,
        nonce: int,
        empieza: int = 0,
        corta_servida_de=(0, 1),
    ):
        self.server_seed = server_seed
        self.client_seed = client_seed
        self.nonce = nonce
        self.empieza = empieza

        # Qué asientos cortan la partida con una generala servida. Son los dos
        # en la generala de verdad, que es simétrica. La excepción es el modo
        # que paga por puntaje: ahí lo que cobrás depende sólo de tu planilla,
        # así que una servida de la casa no tiene por qué cortarte la partida
        # —sería sacarte plata con un volado que no jugaste—, mientras que la
        # tuya sí, porque es un evento de pago tuyo.
        self.corta_servida_de = tuple(corta_servida_de)

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
        - Si este asiento no corta (ver `corta_servida_de`), se anota la
          generala y la partida sigue. Los puntos se ganan igual; lo que no
          pasa es el final anticipado.
        """
        jugador = self.en_turno
        anotada = self.planillas[jugador]["generala"]

        if anotada == 0:
            return

        if jugador not in self.corta_servida_de:
            # Anotar acá cerraría el turno sin pasar por cerrar_turno(), así
            # que no se toca: el turno sigue su curso y el jugador elige. Con
            # cinco iguales en la mano va a anotar la generala igual.
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

    def anoto_generala_servida(self, jugador: int) -> bool:
        """¿Anotó la generala en la primera tirada?

        Sale de la planilla y no de un flag aparte: la generala servida son 60
        puntos y la armada 50, así que el puntaje anotado ya lo dice. Importa
        que se derive del estado reconstruido, porque es lo que hace que el
        premio por servida se pueda verificar desde las acciones guardadas.

        No sirve `generala_servida_de`: ese se setea sólo cuando la servida
        corta la partida, y en el modo que paga por puntaje no corta.
        """
        return self.planillas[jugador]["generala"] == PUNTAJE_SERVIDA["generala"]

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


def reconstruir_desde(
    server_seed, client_seed, nonce, empieza, acciones, corta_servida_de=(0, 1)
) -> Partida:
    """Rehace una partida reproduciendo el registro de acciones.

    Es lo que hace que no haga falta guardar el estado: el flujo de dados se
    consume en orden, así que las mismas acciones sobre el mismo seed dan
    exactamente la misma partida. Lo comparten la mesa contra la casa y la
    mesa entre jugadores, que es donde importa que sea una sola función: si se
    separaran, una podría empezar a reconstruir distinto que la otra y las
    partidas ya jugadas dejarían de verificar.

    No valida de quién era el turno. Eso se chequea al aceptar la acción, no
    al releerla: acá las acciones ya están guardadas y el orden de los turnos
    lo determina el motor.

    `corta_servida_de` tiene que ser el mismo con el que se jugó la partida,
    no el que esté de moda hoy: con otra regla las mismas acciones dan otra
    partida y lo ya jugado deja de verificar. Por eso la fila lo guarda.
    """
    partida = Partida(
        server_seed,
        client_seed,
        nonce,
        empieza=empieza,
        corta_servida_de=corta_servida_de,
    )

    for entrada in acciones:
        if partida.terminada:
            break

        aplicar_accion(partida.turno, entrada["accion"])
        if partida.turno.terminado:
            partida.cerrar_turno()

    return partida
