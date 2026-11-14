from fastapi import APIRouter

from app.modules.games.blackjack.multiplayer_router import router as blackjack_multiplayer_router
from app.modules.games.blackjack.router import router as blackjack_router
from app.modules.games.crash.router import router as crash_router
from app.modules.games.dice.router import router as dice_router
from app.modules.games.poker.multiplayer_router import router as poker_multiplayer_router
from app.modules.games.generala.router import router as generala_router
from app.modules.games.limbo.router import router as limbo_router
from app.modules.games.mines.router import router as mines_router
from app.modules.games.plinko.router import router as plinko_router
from app.modules.games.roulette.router import router as roulette_router
from app.modules.games.slots.router import router as slots_router
from app.modules.games.truco.router import router as truco_router

router = APIRouter(prefix="/games", tags=["Games"])


# El catálogo de juegos vive en el frontend, en `shared/juegos.js`.
#
# Acá había un `GET /games/` que devolvía la lista con su categoría y que no
# llamaba nadie: el lobby tenía las tarjetas escritas a mano. Quedó vieja sin
# que nada lo avisara —le faltaban Mines, Generala y Blackjack Multijugador—
# porque ninguna pantalla la renderizaba, así que un dato equivocado no se
# veía nunca. Dos catálogos que tienen que coincidir y sólo uno a la vista es
# una forma garantizada de que el que no se ve mienta.
#
# Si alguna vez hace falta un catálogo por API —un cliente mobile, un panel
# de administración— que salga de una sola definición y que la consuma algo,
# no de una lista escrita al lado.


router.include_router(roulette_router)
router.include_router(slots_router)
router.include_router(blackjack_router)
router.include_router(blackjack_multiplayer_router)
router.include_router(poker_multiplayer_router)
router.include_router(crash_router)
router.include_router(plinko_router)
router.include_router(mines_router)
router.include_router(generala_router)
router.include_router(truco_router)
router.include_router(dice_router)
router.include_router(limbo_router)
