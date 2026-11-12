"""La partida: manos encadenadas hasta que alguien llega a 30.

Cada mano se reparte del mismo seed con un nonce distinto, así que la partida
entera se puede rehacer después con el server seed revelado.
"""

from app.modules.games.truco.fairness import repartir
from app.modules.games.truco.mano import Mano
from app.modules.games.truco.reglas import PUNTOS_PARTIDA


class Partida:
    def __init__(
        self,
        server_seed: str,
        client_seed: str,
        nonce_base: int,
        mano_inicial: int = 0,
        objetivo: int = PUNTOS_PARTIDA,
        con_flor: bool = False,
    ):
        self.server_seed = server_seed
        self.client_seed = client_seed
        self.nonce_base = nonce_base
        self.objetivo = objetivo
        self.con_flor = con_flor

        self.puntos = [0, 0]
        self.manos_jugadas = 0
        self.proximo_mano = mano_inicial
        self.mano_actual = None
        self.terminada = False
        self.ganador = None

    def nueva_mano(self) -> Mano:
        """Reparte la mano siguiente. El ser mano se alterna."""
        if self.terminada:
            raise RuntimeError("La partida ya terminó")

        if self.mano_actual is not None and not self.mano_actual.terminada:
            raise RuntimeError("La mano anterior sigue abierta")

        self.manos_jugadas += 1
        cartas = repartir(
            self.server_seed, self.client_seed, self.nonce_base + self.manos_jugadas
        )

        self.mano_actual = Mano(
            cartas,
            mano=self.proximo_mano,
            puntos_partida=tuple(self.puntos),
            con_flor=self.con_flor,
        )
        self.proximo_mano = 1 - self.proximo_mano
        return self.mano_actual

    def cerrar_mano(self) -> None:
        """Suma lo que repartió la mano y fija si la partida terminó."""
        if self.mano_actual is None or not self.mano_actual.terminada:
            raise RuntimeError("La mano todavía no terminó")

        for jugador in (0, 1):
            self.puntos[jugador] += self.mano_actual.puntos[jugador]

        # Si los dos pasan el objetivo en la misma mano, gana el que más suma.
        if max(self.puntos) >= self.objetivo:
            self.terminada = True
            self.ganador = 0 if self.puntos[0] > self.puntos[1] else 1

    @property
    def nonce_actual(self) -> int:
        return self.nonce_base + self.manos_jugadas

    def estado(self, para: int = None) -> dict:
        estado = {
            "puntos": list(self.puntos),
            "objetivo": self.objetivo,
            "manos_jugadas": self.manos_jugadas,
            "con_flor": self.con_flor,
            "terminada": self.terminada,
            "ganador": self.ganador,
        }

        if self.mano_actual is not None:
            estado["mano"] = self.mano_actual.estado(para=para)

        return estado
