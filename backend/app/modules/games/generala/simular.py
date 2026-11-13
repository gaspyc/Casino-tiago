"""Mediciones de la generala. No es parte del juego, es la herramienta.

    python -m app.modules.games.generala.simular figuras 20000
    python -m app.modules.games.generala.simular partidas 2000
    python -m app.modules.games.generala.simular contra-simple 2000
    python -m app.modules.games.generala.simular pagos 2000
"""

import sys
from collections import Counter
from decimal import Decimal

from app.modules.games.generala import bot
from app.modules.games.generala.dados import (
    CATEGORIAS,
    CATEGORIAS_NUMERICAS,
    PUNTAJE_ARMADA,
    es_generala,
    puntaje,
)
from app.modules.games.generala.partida import Partida
from app.modules.games.generala.turno import Turno, aplicar_accion
from app.modules.games.shared.semillas import generar_server_seed


def _flujo(nonce):
    from app.modules.games.generala.fairness import FlujoDeDados

    return FlujoDeDados(generar_server_seed(), "simulacion", nonce)


# ------------------------------ figuras ------------------------------

def figuras(vueltas: int) -> None:
    """Con qué frecuencia el bot completa cada categoría en un turno suelto.

    Es lo que decide ORDEN_DE_SACRIFICIO: la fila que menos rinde se tacha
    primero. Cada turno se juega con todas las categorías libres, así que mide
    la chance de la figura y no el efecto de la planilla.
    """
    logradas = Counter()
    suma_numeros = Counter()

    for vuelta in range(vueltas):
        turno = Turno(_flujo(vuelta), CATEGORIAS)

        while turno.puede_tirar:
            indices = bot.elegir_dados(turno)
            if not indices:
                break
            turno.tirar(indices)

        for categoria in CATEGORIAS:
            puntos = puntaje(categoria, turno.dados, servida=turno.servida)
            if categoria in CATEGORIAS_NUMERICAS:
                suma_numeros[categoria] += puntos
            elif puntos:
                logradas[categoria] += 1

    print("categoria  | sale en      | paga | valor esperado")
    print("-" * 52)

    filas = []
    for categoria in CATEGORIAS:
        if categoria in CATEGORIAS_NUMERICAS:
            esperado = suma_numeros[categoria] / vueltas
            filas.append((categoria, None, esperado))
        else:
            probabilidad = logradas[categoria] / vueltas
            esperado = PUNTAJE_ARMADA[categoria] * probabilidad
            filas.append((categoria, probabilidad, esperado))

    for categoria, probabilidad, esperado in filas:
        chance = "%.2f%%" % (probabilidad * 100) if probabilidad is not None else "-"
        paga = PUNTAJE_ARMADA.get(categoria, "suma")
        print("%-10s | %-12s | %-4s | %.2f" % (categoria, chance, paga, esperado))

    print()
    print("orden sugerido (de menor a mayor valor esperado):")
    print("   ", [categoria for categoria, _, _ in sorted(filas, key=lambda f: f[2])])
    print("orden en el bot:")
    print("   ", list(bot.ORDEN_DE_SACRIFICIO))


# ------------------------------ partidas ------------------------------

def _jugar(semilla, nonce, politicas, empieza=0):
    """Una partida entre dos políticas. Devuelve (ganador, totales).

    `empieza` es el asiento que arranca. Va aparte del nonce a propósito:
    atarlo al nonce y además alternar los asientos por la misma paridad hacía
    que uno de los dos arrancara siempre, que es justo lo que se quiere
    cancelar.
    """
    partida = Partida(semilla, "simulacion", nonce, empieza=empieza)

    while not partida.terminada:
        jugador = partida.en_turno
        accion = politicas[jugador](partida, jugador)
        if accion is None:
            break

        aplicar_accion(partida.turno, accion)
        if partida.turno.terminado:
            partida.cerrar_turno()

    return partida.ganador, [partida.total(0), partida.total(1)]


def _dados_por_heuristica(turno) -> list:
    """Cómo elegía los dados el bot antes de que calculara.

    Perseguir el grupo más grande, o la escalera si falta un solo dado. Son
    las reglas que cualquiera aplicaría jugando en una mesa, y por eso sirven
    de proxy de un jugador humano razonable. Se conservan acá, fuera del bot,
    justamente para medir contra qué se lo comparó.
    """
    from collections import Counter

    from app.modules.games.generala.dados import DADOS, ESCALERAS

    dados = turno.dados
    cuenta = Counter(dados)
    disponibles = set(turno.disponibles)

    if max(cuenta.values()) == DADOS:
        return []

    if "escalera" in disponibles and tuple(sorted(dados)) in ESCALERAS:
        return []

    if "full" in disponibles and sorted(cuenta.values()) == [2, 3]:
        if "poker" not in disponibles and "generala" not in disponibles:
            return []

    if "escalera" in disponibles and max(cuenta.values()) < 3:
        for escalera in ESCALERAS:
            if len(set(escalera) - set(dados)) != 1:
                continue

            vistos = set()
            sobrantes = []
            for indice, dado in enumerate(dados):
                if dado in escalera and dado not in vistos:
                    vistos.add(dado)
                else:
                    sobrantes.append(indice)

            if len(sobrantes) == 1:
                return sobrantes

    cara, _ = max(cuenta.items(), key=lambda par: (par[1], par[0]))
    return [indice for indice, dado in enumerate(dados) if dado != cara]


def _politica_heuristica(partida, jugador):
    """El proxy de jugador humano: reglas de dedo para los dados, anotar lo máximo."""
    turno = partida.turno
    if turno.puede_tirar:
        indices = _dados_por_heuristica(turno)
        if indices:
            return "tirar:%s" % ",".join(str(indice) for indice in indices)

    puntajes = turno.puntajes()
    return "anotar:%s" % max(puntajes, key=lambda categoria: puntajes[categoria])


def _politica_simple(partida, jugador):
    """Como el bot para los dados, pero anota siempre lo máximo.

    Aísla cuánto vale la parte de elegir dónde anotar: lo único que lo separa
    del bot es el orden de sacrificio y no quemar filas caras.

    OJO: esto NO es una línea de base débil, aunque el nombre lo sugiera.
    Elige los dados llamando a `bot.elegir_dados`, así que cuando al bot se le
    puso el cálculo exacto esta política se volvió fuerte sola, sin que nadie
    la tocara. Medida: saca el mismo puntaje que la calculadora. El piso de
    verdad es `_politica_heuristica`, que tiene su propia copia congelada de
    cómo elegía los dados el bot viejo, justamente para no contagiarse.

    Ya me comió una conclusión una vez: con esta política como "rival tonto"
    parecía que en la generala pensar no pagaba nada, y lo que pasaba era que
    el rival tonto estaba pensando igual que el bot.
    """
    turno = partida.turno
    if turno.puede_tirar:
        indices = bot.elegir_dados(turno)
        if indices:
            return "tirar:%s" % ",".join(str(indice) for indice in indices)

    puntajes = turno.puntajes()
    return "anotar:%s" % max(puntajes, key=lambda categoria: puntajes[categoria])


def _politica_azarosa(partida, jugador):
    """El piso: vuelve a tirar dados al azar y anota lo que mas da.

    Sirve para ver cuanto vale la decision de que dados guardar, que es la
    unica parte de la generala donde se puede pensar de verdad.
    """
    import random

    turno = partida.turno
    if turno.puede_tirar:
        cuantos = random.randint(0, 5)
        if cuantos:
            indices = random.sample(range(5), cuantos)
            return "tirar:%s" % ",".join(str(indice) for indice in sorted(indices))

    puntajes = turno.puntajes()
    return "anotar:%s" % max(puntajes, key=lambda categoria: puntajes[categoria])


def _mejor_anotacion(dados, disponibles, servida):
    """El mejor puntaje que se puede sacar con estos dados."""
    return max(puntaje(categoria, dados, servida) for categoria in disponibles)


_CACHE_ESPERADO = {}


def _tiradas_posibles(cantidad):
    """Los resultados de tirar `cantidad` dados, como multiconjuntos con peso.

    Enumerar las 6^5 = 7776 tiradas ordenadas es tirar trabajo: lo que importa
    es el multiconjunto, y hay 252. Cada uno pesa por su coeficiente
    multinomial. Mismo resultado exacto, treinta veces más rápido.
    """
    from collections import Counter
    from itertools import combinations_with_replacement
    from math import factorial

    salida = []
    for combinacion in combinations_with_replacement(range(1, 7), cantidad):
        repeticiones = Counter(combinacion)
        peso = factorial(cantidad)
        for veces in repeticiones.values():
            peso //= factorial(veces)
        salida.append((combinacion, peso))

    return salida


_POSIBLES = {cantidad: _tiradas_posibles(cantidad) for cantidad in range(6)}


def _esperado_guardando(guardados, faltan, disponibles):
    """E[mejor puntaje] si se tiran `faltan` dados y se queda con `guardados`.

    Exacto: enumera, no simula.
    """
    clave = (tuple(sorted(guardados)), faltan, tuple(sorted(disponibles)))
    if clave in _CACHE_ESPERADO:
        return _CACHE_ESPERADO[clave]

    if faltan == 0:
        valor = float(_mejor_anotacion(list(guardados), disponibles, False))
    else:
        total = 0
        peso_total = 0
        for tirada, peso in _POSIBLES[faltan]:
            puntos = _mejor_anotacion(
                list(guardados) + list(tirada), disponibles, False
            )
            total += puntos * peso
            peso_total += peso

        valor = total / peso_total

    _CACHE_ESPERADO[clave] = valor
    return valor


def _politica_calculadora(partida, jugador):
    """El techo practico: mira una tirada adelante y enumera, no simula.

    En la ultima oportunidad de tirar elige el subconjunto a guardar que
    maximiza el puntaje esperado, calculado sobre las 6^k tiradas posibles.
    Es mucho mas fuerte que cualquier heuristica y mas lento, por eso vive
    aca y no en el bot: sirve para medir cuanto le puede sacar un jugador
    perfecto a la casa.
    """
    from itertools import combinations

    turno = partida.turno
    disponibles = turno.disponibles

    if turno.puede_tirar:
        mejor_valor = None
        mejor_indices = None

        for cantidad in range(6):
            for guardar in combinations(range(5), cantidad):
                guardados = [turno.dados[indice] for indice in guardar]
                valor = _esperado_guardando(guardados, 5 - cantidad, disponibles)

                if mejor_valor is None or valor > mejor_valor:
                    mejor_valor = valor
                    mejor_indices = [i for i in range(5) if i not in guardar]

        # Quedarse quieto solo si anotar ya supera lo que da tirar.
        ahora = _mejor_anotacion(turno.dados, disponibles, turno.servida)
        if mejor_indices and mejor_valor > ahora:
            return "tirar:%s" % ",".join(str(indice) for indice in mejor_indices)

    puntajes = turno.puntajes()
    return "anotar:%s" % max(puntajes, key=lambda categoria: puntajes[categoria])


def _duelo_politicas(vueltas, politica_a, politica_b, semilla):
    gana_a = 0
    empates = 0
    puntos_a = 0
    puntos_b = 0

    for nonce in range(vueltas):
        asiento = nonce % 2
        politicas = (
            [politica_a, politica_b] if asiento == 0 else [politica_b, politica_a]
        )
        ganador, totales = _jugar(
            semilla, nonce, politicas, empieza=(nonce // 2) % 2
        )

        puntos_a += totales[asiento]
        puntos_b += totales[1 - asiento]
        if ganador is None:
            empates += 1
        elif ganador == asiento:
            gana_a += 1

    decididas = vueltas - empates
    return gana_a / decididas, puntos_a / vueltas, puntos_b / vueltas


def rivales(vueltas: int) -> None:
    """El bot contra el piso y contra el techo. Es lo que fija el pago.

    Si el techo le gana mucho al bot, un jugador que estudia rompe la casa y
    el multiplicador de pago tiene que bajar. Si le gana poco, la generala es
    un juego de dados y el pago puede ser generoso.
    """
    semilla = generar_server_seed()

    for nombre, rival in (
        ("azarosa (piso)", _politica_azarosa),
        ("heuristica (humano)", _politica_heuristica),
        ("dados del bot, anota max", _politica_simple),
        ("calculadora (techo)", _politica_calculadora),
    ):
        tasa, propios, ajenos = _duelo_politicas(vueltas, bot.decidir, rival, semilla)
        print(
            "bot vs %-20s | gana el bot %5.1f%% | %.1f a %.1f puntos"
            % (nombre, tasa * 100, propios, ajenos)
        )


def partidas(vueltas: int) -> None:
    """Bot contra sí mismo: tiene que dar 50% o hay sesgo de asiento."""
    semilla = generar_server_seed()
    gana_cero = 0
    totales = []

    for nonce in range(vueltas):
        ganador, puntos = _jugar(
            semilla, nonce, [bot.decidir, bot.decidir], empieza=nonce % 2
        )
        gana_cero += 1 if ganador == 0 else 0
        totales.extend(puntos)

    print("partidas:           %s" % vueltas)
    print("gana el jugador 0:  %.1f%%" % (100 * gana_cero / vueltas))
    print("puntaje promedio:   %.1f" % (sum(totales) / len(totales)))
    print("puntaje maximo:     %s" % max(totales))


def contra_simple(vueltas: int) -> None:
    """Cuánto vale pensar: el bot contra el que sólo anota lo más alto."""
    semilla = generar_server_seed()
    gana_bot = 0
    empates = 0
    puntos_bot = []
    puntos_simple = []

    for nonce in range(vueltas):
        # Se alternan los asientos para que empezar no decida la medición.
        asiento_bot = nonce % 2
        if asiento_bot == 0:
            politicas = [bot.decidir, _politica_simple]
        else:
            politicas = [_politica_simple, bot.decidir]

        ganador, puntos = _jugar(
            semilla, nonce, politicas, empieza=(nonce // 2) % 2
        )
        puntos_bot.append(puntos[asiento_bot])
        puntos_simple.append(puntos[1 - asiento_bot])

        if ganador is None:
            empates += 1
        elif ganador == asiento_bot:
            gana_bot += 1

    decididas = vueltas - empates
    print("partidas:            %s (%s empates)" % (vueltas, empates))
    print("gana el bot:         %.1f%% de las decididas" % (100 * gana_bot / decididas))
    print("puntaje bot:         %.1f" % (sum(puntos_bot) / vueltas))
    print("puntaje del simple:  %.1f" % (sum(puntos_simple) / vueltas))


def _con_orden(orden):
    """Una politica igual al bot pero con otro orden de sacrificio."""
    def politica(partida, jugador):
        viejo = bot.ORDEN_DE_SACRIFICIO
        bot.ORDEN_DE_SACRIFICIO = orden
        try:
            return bot.decidir(partida, jugador)
        finally:
            bot.ORDEN_DE_SACRIFICIO = viejo

    return politica


CANDIDATOS = {
    # El que supuse de entrada, por intuicion.
    "supuesto": ("1", "generala", "2", "poker", "3", "escalera", "full", "4", "5", "6"),
    # El que sugiere el valor esperado por turno, medido con `figuras`.
    "por-ev": ("1", "2", "full", "generala", "3", "escalera", "4", "5", "6", "poker"),
    # Numeros bajos primero y figuras caras al final, el consejo clasico.
    "clasico": ("1", "2", "3", "full", "escalera", "generala", "4", "5", "poker", "6"),
    # Resignar temprano lo improbable: generala y full son las que menos salen.
    "resigna-raras": ("1", "generala", "full", "2", "3", "escalera", "4", "5", "6", "poker"),
    # Las figuras ultimas de todo.
    "figuras-ultimas": ("1", "2", "3", "4", "5", "6", "full", "generala", "escalera", "poker"),
}


def _duelo(vueltas, orden_a, orden_b, semilla):
    """Dos ordenes cara a cara, alternando quien empieza."""
    gana_a = 0
    empates = 0
    puntos_a = 0
    puntos_b = 0

    for nonce in range(vueltas):
        asiento = nonce % 2
        if asiento == 0:
            politicas = [_con_orden(orden_a), _con_orden(orden_b)]
        else:
            politicas = [_con_orden(orden_b), _con_orden(orden_a)]

        # Arranca uno y otro por turnos, independiente del asiento, así ni el
        # asiento ni el empezar quedan pegados a una de las dos políticas.
        ganador, totales = _jugar(
            semilla, nonce, politicas, empieza=(nonce // 2) % 2
        )
        puntos_a += totales[asiento]
        puntos_b += totales[1 - asiento]

        if ganador is None:
            empates += 1
        elif ganador == asiento:
            gana_a += 1

    decididas = vueltas - empates
    return gana_a / decididas, puntos_a / vueltas, puntos_b / vueltas


def ordenes(vueltas: int) -> None:
    """Cada candidato contra el mismo rival de referencia.

    El rival es el orden "supuesto", que es el que estaba escrito en el bot.
    Lo que importa es la columna de puntaje: ganar o perder por un punto en el
    marcador depende mucho del azar de los dados, el puntaje promedio es mas
    estable.
    """
    semilla = generar_server_seed()
    referencia = CANDIDATOS["supuesto"]

    print("%s partidas por duelo, contra el orden 'supuesto'" % vueltas)
    print()
    print("%-16s | %-10s | %-8s | %s" % ("orden", "gana", "sus ptos", "ptos rival"))
    print("-" * 56)

    for nombre, orden in CANDIDATOS.items():
        if nombre == "supuesto":
            continue

        tasa, propios, ajenos = _duelo(vueltas, orden, referencia, semilla)
        print("%-16s | %8.1f%% | %8.1f | %.1f" % (nombre, tasa * 100, propios, ajenos))


# ------------------------------ la tabla de pagos ------------------------------

def _politica_optima(partida, jugador):
    """El juego perfecto, resuelto por programación dinámica en `optimo.py`."""
    from app.modules.games.generala.optimo import jugada_optima
    from app.modules.games.generala.pagos import (
        PREMIO_SERVIDA,
        PUNTAJE_DE_EQUILIBRIO,
    )

    # El premio en puntos: con pago afín, un premio de J multiplicadores
    # equivale a J/a puntos. Hace falta para que el óptimo cuide la generala.
    bonus = float(PREMIO_SERVIDA) * PUNTAJE_DE_EQUILIBRIO

    turno = partida.turno
    que, cual = jugada_optima(turno.dados, turno.disponibles, turno.tirada, bonus)

    if que == "anotar":
        return "anotar:%s" % cual

    return "tirar:%s" % ",".join(str(indice) for indice in cual)


def _planilla(politica, semilla, nonce):
    """Juega una planilla entera y devuelve (puntaje, anotó generala servida).

    corta_servida_de=() porque en el modo que paga por puntaje la servida no
    corta la partida: la de la casa no tiene por qué cortarte —sería sacarte
    plata con un volado que no jugaste— y la tuya se cobra aparte.
    """
    partida = Partida(semilla, "pagos", nonce, empieza=0, corta_servida_de=())
    servida = False

    while not partida.terminada:
        turno = partida.turno
        # Ojo: no alcanza con que salgan cinco iguales. El premio es por
        # ANOTAR la generala servida; si la fila ya se usó, no hay premio.
        podia = partida.en_turno == 0 and turno.servida and es_generala(turno.dados)

        aplicar_accion(turno, politica(partida, partida.en_turno))

        if podia and turno.terminado and turno.categoria == "generala":
            servida = True

        if partida.turno.terminado:
            partida.cerrar_turno()

    return partida.total(0), servida


def pagos(vueltas: int) -> None:
    """El RTP de cada política bajo la tabla de pagos, contra el techo exacto.

    El techo no se simula, se resuelve. Es la diferencia entre saber la
    ventaja de la casa y estimarla con el mejor bot que uno pudo escribir.
    """
    from app.modules.games.generala.optimo import techo_del_pago
    from app.modules.games.generala.pagos import (
        PREMIO_SERVIDA,
        PUNTAJE_DE_EQUILIBRIO,
        RTP_OBJETIVO,
        premio,
    )

    por_punto = 1.0 / PUNTAJE_DE_EQUILIBRIO
    techo = techo_del_pago(0.0, por_punto, float(PREMIO_SERVIDA))

    print("equilibrio %s puntos, servida paga %sx aparte"
          % (PUNTAJE_DE_EQUILIBRIO, PREMIO_SERVIDA))
    print("techo exacto (juego perfecto): %.2f%%   objetivo %.2f%%"
          % (100 * techo, 100 * float(RTP_OBJETIVO)))
    print()

    semilla = generar_server_seed()
    apuesta = Decimal("100.00")

    print("%-22s | puntos | servida | RTP    | sigma" % "politica")
    print("-" * 66)

    for nombre, politica in (
        ("optimo (con premio)", _politica_optima),
        ("bot de la casa", bot.decidir),
        ("calculadora (1 vista)", _politica_calculadora),
        ("heuristica (casual)", _politica_heuristica),
        ("azarosa (piso)", _politica_azarosa),
    ):
        suma_puntos = 0
        servidas = 0
        pagado = []

        for nonce in range(vueltas):
            puntaje, servida = _planilla(politica, semilla, nonce)
            suma_puntos += puntaje
            servidas += 1 if servida else 0
            pagado.append(float(premio(apuesta, puntaje, servida)) / 100.0)

        media = sum(pagado) / len(pagado)
        varianza = sum((x - media) ** 2 for x in pagado) / len(pagado)

        print("%-22s | %6.1f | %6.2f%% | %5.1f%% | %5.2f"
              % (nombre, suma_puntos / vueltas, 100 * servidas / vueltas,
                 100 * media, varianza ** 0.5))

        if media > techo + 0.02:
            print("   *** %s le gana al techo: la tabla esta mal calibrada" % nombre)

    print()
    print("con pago binario 1.95x era: optimo ~93.9%, casual 68.6%")
    print()
    print("OJO con pocas vueltas: la servida sale una vez cada ~160 planillas y")
    print("paga 17x, asi que aporta ~13% del RTP con muy pocos eventos. Con")
    print("%s vueltas son ~%d servidas por politica y el RTP baila varios puntos."
          % (vueltas, vueltas * 0.0063))
    print("Los numeros del docstring de pagos.py son sobre 400.000 planillas.")


if __name__ == "__main__":
    comando = sys.argv[1] if len(sys.argv) > 1 else "figuras"
    vueltas = int(sys.argv[2]) if len(sys.argv) > 2 else 2000

    {
        "figuras": figuras,
        "partidas": partidas,
        "contra-simple": contra_simple,
        "ordenes": ordenes,
        "rivales": rivales,
        "pagos": pagos,
    }[comando](vueltas)
