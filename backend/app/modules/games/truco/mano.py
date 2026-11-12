"""La mano de truco: una repartida de tres cartas, con sus cantos.

Es pura: entra el reparto y las acciones de los jugadores, y sale quién ganó y
cuántos puntos. No sabe de base de datos, ni de plata, ni de quién es el bot.

Los jugadores son 0 y 1. El que es mano juega primero y gana las pardas.
Variante 1v1: envido / real envido / falta envido y truco / retruco / vale
cuatro. La flor es opcional (`con_flor`): cuando está prendida, el que la
tiene la canta en la primera y mata el envido.
"""

from app.modules.games.truco import reglas
from app.modules.games.truco.cartas import (
    comparar,
    puntos_envido,
    tantos_de_flor,
    tiene_flor,
)

JUGADORES = (0, 1)
PARDA = reglas.PARDA

QUIERO = "quiero"
NO_QUIERO = "no_quiero"
IRSE_AL_MAZO = "irse_al_mazo"


class AccionInvalida(Exception):
    """La acción no está permitida en este momento de la mano."""


def _rival(jugador: int) -> int:
    return 1 - jugador


class Mano:
    def __init__(self, cartas, mano: int = 0, puntos_partida=(0, 0), con_flor: bool = False):
        if len(cartas) != 2 or any(len(mazo) != 3 for mazo in cartas):
            raise ValueError("Se reparten tres cartas a cada uno de los dos jugadores")

        self.cartas = [list(mazo) for mazo in cartas]
        self.mano = mano
        self.turno = mano
        self.puntos_partida = list(puntos_partida)

        self.rondas = []            # cada ronda: lista de (jugador, carta)
        self.resultados = []        # ganador de cada ronda, o PARDA

        self.cantos_truco = []
        self.truco_querido = False
        self.cantos_envido = []
        self.envido_resuelto = False

        self.con_flor = con_flor
        self.cantos_flor = []
        self.flor_resuelta = False

        # Canto esperando respuesta: {"canto": str, "de": int, "familia": str}
        self.pendiente = None

        self.terminada = False
        self.ganador = None
        self.puntos = [0, 0]
        self.envido_cantado_por = None
        self.flor_cantada_por = None

    # ------------------------------ consultas ------------------------------

    @property
    def ronda_actual(self):
        if self.rondas and len(self.rondas[-1]) < 2:
            return self.rondas[-1]

        return None

    def _en_primera(self) -> bool:
        """El envido se canta mientras no se haya terminado la primera ronda."""
        return not self.resultados

    def _envido_disponible(self) -> bool:
        return self._en_primera() and not self.envido_resuelto and not self.cantos_flor

    def tiene_flor(self, jugador: int) -> bool:
        """Mira las tres cartas repartidas, estén jugadas o no."""
        return self.con_flor and tiene_flor(self._cartas_repartidas(jugador))

    def _flor_disponible(self, jugador: int) -> bool:
        return (
            self._en_primera()
            and not self.flor_resuelta
            and self.tiene_flor(jugador)
            and jugador != self.flor_cantada_por
        )

    def _cartas_repartidas(self, jugador: int) -> list:
        jugadas = [
            carta for ronda in self.rondas for quien, carta in ronda if quien == jugador
        ]
        return self.cartas[jugador] + jugadas

    def acciones(self, jugador: int) -> list:
        """Lo que el jugador puede hacer ahora mismo."""
        if self.terminada:
            return []

        if self.pendiente is not None:
            if jugador == self.pendiente["de"]:
                return []

            responde = _rival(self.pendiente["de"])
            familia = self.pendiente["familia"]

            if familia == "flor":
                # A la flor sola no se le dice quiero: o se la supera con
                # contraflor, o son buenas. A la contraflor sí, y ahí se
                # comparan las flores.
                if self.pendiente["canto"] == "flor":
                    return self._cantos_de_flor_posibles(responde) + [NO_QUIERO]

                return [QUIERO, NO_QUIERO] + self._cantos_de_flor_posibles(responde)

            # Con flor en la mano el envido no se contesta: se canta flor encima.
            if familia == "envido" and self._flor_disponible(responde):
                return ["flor"]

            acciones = [QUIERO, NO_QUIERO]
            acciones += self._subidas_posibles()
            return acciones

        if jugador != self.turno:
            return []

        acciones = ["jugar:%s" % carta for carta in self.cartas[jugador]]
        acciones.append(IRSE_AL_MAZO)

        if self._flor_disponible(jugador):
            acciones.append("flor")

        if self._envido_disponible():
            acciones += self._cantos_de_envido_posibles(jugador)

        acciones += self._cantos_de_truco_posibles()
        return acciones

    def _cantos_de_flor_posibles(self, jugador: int) -> list:
        """Con qué puede contestar una flor el que también tiene flor."""
        if not self.tiene_flor(jugador):
            return []

        ultimo = self.cantos_flor[-1] if self.cantos_flor else None
        if ultimo == "contraflor_al_resto":
            return []

        if ultimo == "flor":
            return ["contraflor", "contraflor_al_resto"]

        return ["contraflor_al_resto"]

    def _cantos_de_truco_posibles(self) -> list:
        if not self.cantos_truco:
            return ["truco"]

        # Sólo puede subir el que no cantó último, y únicamente si ya se quiso.
        if not self.truco_querido:
            return []

        siguiente = reglas.ESCALERA_TRUCO.index(self.cantos_truco[-1]) + 1
        if siguiente >= len(reglas.ESCALERA_TRUCO):
            return []

        return [reglas.ESCALERA_TRUCO[siguiente]]

    def _cantos_de_envido_posibles(self, jugador: int = None) -> list:
        # Con flor en la mano no se canta envido: se canta flor.
        if jugador is not None and self.tiene_flor(jugador):
            return []

        if not self.cantos_envido:
            return ["envido", "real_envido", "falta_envido"]

        ultimo = self.cantos_envido[-1]
        if ultimo == "falta_envido":
            return []

        if ultimo == "envido":
            return ["envido", "real_envido", "falta_envido"]

        return ["falta_envido"]

    def _subidas_posibles(self) -> list:
        """Con qué se puede contestar un canto sin quererlo ni rechazarlo."""
        familia = self.pendiente["familia"]
        responde = _rival(self.pendiente["de"])

        if familia == "envido":
            return self._cantos_de_envido_posibles(responde)

        # El envido está primero: se puede meter envido sobre un truco de la
        # primera ronda antes de contestarlo.
        subidas = []
        if self._flor_disponible(responde):
            subidas.append("flor")

        if self._envido_disponible():
            subidas += self._cantos_de_envido_posibles(responde)

        siguiente = reglas.ESCALERA_TRUCO.index(self.cantos_truco[-1]) + 1
        if siguiente < len(reglas.ESCALERA_TRUCO):
            subidas.append(reglas.ESCALERA_TRUCO[siguiente])

        return subidas

    # ------------------------------ acciones ------------------------------

    def jugar(self, jugador: int, carta: str) -> None:
        self._validar("jugar:%s" % carta, jugador)

        self.cartas[jugador].remove(carta)

        if self.ronda_actual is None:
            self.rondas.append([])

        self.rondas[-1].append((jugador, carta))

        if len(self.rondas[-1]) == 2:
            self._resolver_ronda()
        else:
            self.turno = _rival(jugador)

    def cantar(self, jugador: int, canto: str) -> None:
        self._validar(canto, jugador)

        if canto in reglas.ESCALERA_FLOR:
            self._cantar_flor(jugador, canto)
            return

        familia = "envido" if canto in reglas.ESCALERA_ENVIDO else "truco"

        if familia == "envido":
            self.cantos_envido.append(canto)
            if self.envido_cantado_por is None:
                self.envido_cantado_por = jugador
        else:
            self.cantos_truco.append(canto)
            self.truco_querido = False

        self.pendiente = {"canto": canto, "de": jugador, "familia": familia}

    def _cantar_flor(self, jugador: int, canto: str) -> None:
        # La flor cantada sobre un envido lo deja sin efecto.
        if self.pendiente is not None and self.pendiente["familia"] == "envido":
            self.cantos_envido = []
            self.envido_resuelto = True

        self.cantos_flor.append(canto)
        if self.flor_cantada_por is None:
            self.flor_cantada_por = jugador

        rival = _rival(jugador)

        # Si el rival no tiene flor no hay nada que discutir: se cobra.
        if not self.tiene_flor(rival):
            self.pendiente = None
            self._resolver_flor(jugador, querido=False, sin_rival=True)
            return

        self.pendiente = {"canto": canto, "de": jugador, "familia": "flor"}

    def responder(self, jugador: int, respuesta: str) -> None:
        self._validar(respuesta, jugador)

        familia = self.pendiente["familia"]
        quien_canto = self.pendiente["de"]
        self.pendiente = None

        if familia == "flor":
            self._resolver_flor(quien_canto, querido=respuesta == QUIERO)
            return

        if familia == "envido":
            self._resolver_envido(quien_canto, respuesta == QUIERO)
            return

        if respuesta == NO_QUIERO:
            self._terminar(quien_canto, reglas.puntos_truco(self.cantos_truco, False))
            return

        self.truco_querido = True

    def irse_al_mazo(self, jugador: int) -> None:
        self._validar(IRSE_AL_MAZO, jugador)

        # Lo que valga el truco hasta acá se lo lleva el rival.
        self._terminar(_rival(jugador), reglas.puntos_truco(self.cantos_truco, self.truco_querido))

    def _validar(self, accion: str, jugador: int) -> None:
        if jugador not in JUGADORES:
            raise AccionInvalida("Jugador inexistente")

        if accion not in self.acciones(jugador):
            raise AccionInvalida(
                "'%s' no está permitida para el jugador %s ahora" % (accion, jugador)
            )

    # ------------------------------ resolución ------------------------------

    def _resolver_envido(self, quien_canto: int, querido: bool) -> None:
        self.envido_resuelto = True

        if not querido:
            puntos = reglas.puntos_envido(self.cantos_envido, False)
            self._sumar(quien_canto, puntos)
            return

        rival = _rival(quien_canto)
        puntos_canto = reglas.puntos_envido(
            self.cantos_envido, True, self.puntos_partida[0], self.puntos_partida[1]
        )

        tantos = [self._tantos(0), self._tantos(1)]
        gana_quien_canto = reglas.gana_el_envido(
            tantos[quien_canto], tantos[rival], jugador_es_mano=(self.mano == quien_canto)
        )

        self._sumar(quien_canto if gana_quien_canto else rival, puntos_canto)

    def _resolver_flor(self, quien_canto: int, querido: bool, sin_rival: bool = False) -> None:
        """La flor también mata al envido: no se juega más en esta mano."""
        self.flor_resuelta = True
        self.envido_resuelto = True

        puntos = reglas.puntos_flor(
            self.cantos_flor, querido, self.puntos_partida[0], self.puntos_partida[1]
        )

        if sin_rival or not querido:
            self._sumar(quien_canto, puntos)
            return

        rival = _rival(quien_canto)
        gana_quien_canto = reglas.gana_la_flor(
            tantos_de_flor(self._cartas_repartidas(quien_canto)),
            tantos_de_flor(self._cartas_repartidas(rival)),
            jugador_es_mano=(self.mano == quien_canto),
        )

        self._sumar(quien_canto if gana_quien_canto else rival, puntos)

    def _tantos(self, jugador: int) -> int:
        """Los puntos de envido de la mano repartida, estén jugadas o no."""
        return puntos_envido(self._cartas_repartidas(jugador))

    def _resolver_ronda(self) -> None:
        (primero, carta_primero), (segundo, carta_segundo) = self.rondas[-1]
        resultado = comparar(carta_primero, carta_segundo)

        if resultado == 0:
            self.resultados.append(PARDA)
            self.turno = primero
        else:
            ganador = primero if resultado > 0 else segundo
            self.resultados.append(ganador)
            self.turno = ganador

        ganador_mano = reglas.ganador_de_la_mano(self.resultados, mano=self.mano)
        if ganador_mano is not None:
            self._terminar(
                ganador_mano, reglas.puntos_truco(self.cantos_truco, self.truco_querido)
            )

    def _terminar(self, ganador: int, puntos: int) -> None:
        self._sumar(ganador, puntos)
        self.ganador = ganador
        self.terminada = True
        self.pendiente = None

    def _sumar(self, jugador: int, puntos: int) -> None:
        self.puntos[jugador] += puntos

    # ------------------------------ estado ------------------------------

    def estado(self, para: int = None) -> dict:
        """Lo que se puede mostrar. Con `para`, oculta las cartas del rival."""
        estado = {
            "mano": self.mano,
            "turno": self.turno,
            "rondas": [[{"jugador": j, "carta": c} for j, c in ronda] for ronda in self.rondas],
            "resultados": list(self.resultados),
            "cantos_truco": list(self.cantos_truco),
            "truco_querido": self.truco_querido,
            "cantos_envido": list(self.cantos_envido),
            "envido_resuelto": self.envido_resuelto,
            "con_flor": self.con_flor,
            "cantos_flor": list(self.cantos_flor),
            "flor_resuelta": self.flor_resuelta,
            "pendiente": dict(self.pendiente) if self.pendiente else None,
            "terminada": self.terminada,
            "ganador": self.ganador,
            "puntos": list(self.puntos),
        }

        if para is None:
            estado["cartas"] = [list(mazo) for mazo in self.cartas]
        else:
            estado["cartas"] = list(self.cartas[para])
            estado["cartas_del_rival"] = len(self.cartas[_rival(para)])
            estado["acciones"] = self.acciones(para)
            estado["tengo_flor"] = self.tiene_flor(para)

        return estado


def jugador_en_turno(mano: Mano):
    """A quién le toca hablar: el que debe contestar un canto, o el del turno."""
    if mano.terminada:
        return None

    if mano.pendiente is not None:
        return _rival(mano.pendiente["de"])

    return mano.turno


def aplicar_accion(mano: Mano, jugador: int, accion: str) -> None:
    """Aplica una de las acciones que devuelve `Mano.acciones`."""
    if accion.startswith("jugar:"):
        mano.jugar(jugador, accion.split(":", 1)[1])
    elif accion in (QUIERO, NO_QUIERO):
        mano.responder(jugador, accion)
    elif accion == IRSE_AL_MAZO:
        mano.irse_al_mazo(jugador)
    else:
        mano.cantar(jugador, accion)
