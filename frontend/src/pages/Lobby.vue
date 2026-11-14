<template>
  <div class="lobby-container">
    <div class="dashboard">
      <section
        v-for="grupo in GRUPOS"
        :key="grupo.id"
        class="grupo"
        :style="{ '--acento': grupo.color }"
      >
        <header class="grupo-head">
          <span class="grupo-marca">{{ grupo.icono }}</span>
          <div class="grupo-texto">
            <h3>{{ grupo.titulo }}</h3>
            <p>{{ grupo.bajada }}</p>
          </div>
          <span class="grupo-cuenta">{{ juegosDe(grupo.id).length }}</span>
        </header>

        <div class="games-grid">
          <article
            v-for="juego in juegosDe(grupo.id)"
            :key="juego.id"
            class="game-card"
            :style="{ '--color-juego': juego.color }"
            tabindex="0"
            @click="router.push(juego.ruta)"
            @keyup.enter="router.push(juego.ruta)"
          >
            <div class="portada" :class="'patron-' + juego.patron">
              <span class="portada-glifo">{{ juego.icono }}</span>
              <span v-if="juego.cta" class="portada-cta">{{ juego.cta }}</span>
            </div>

            <div class="game-cuerpo">
              <div class="game-titulo">
                <h4>{{ juego.nombre }}</h4>
                <span
                  v-for="marca in juego.marcas"
                  :key="marca"
                  class="marca"
                  :class="MARCAS[marca].clase"
                >
                  {{ MARCAS[marca].texto }}
                </span>
              </div>
              <p>{{ juego.descripcion }}</p>
            </div>
          </article>
        </div>
      </section>
    </div>

    <TransactionTable />
  </div>
</template>

<script setup>
// El saldo, el deposito y el retiro viven en la barra de arriba (App.vue):
// el saldo se muestra en todas las pantallas, asi que repetirlo aca en una
// tarjeta gigante lo dejaba dos veces en la misma pantalla y empujaba los
// juegos abajo del pliegue.
import { useRouter } from 'vue-router';
import { GRUPOS, MARCAS, juegosDe } from '../shared/juegos';
import TransactionTable from '../widgets/TransactionTable.vue';

const router = useRouter();
</script>

<style scoped>
.lobby-container {
  padding: 22px 40px 40px;
  max-width: var(--ancho-maximo, 1680px);
  margin: 0 auto;
  width: 100%;
}

.dashboard {
  display: flex;
  flex-direction: column;
}

/* ------------------------------ las secciones ------------------------------
   El encabezado deja de ser texto suelto: una marca con el color de la
   seccion lo ancla a la izquierda, el conteo cierra a la derecha, y una
   linea que se desvanece lo separa del contenido sin cortar la pagina con
   una regla dura de lado a lado. */

.grupo {
  margin-bottom: 34px;
}

.grupo-head {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 16px;
  padding-bottom: 12px;
  position: relative;
}

.grupo-head::after {
  content: '';
  position: absolute;
  left: 0;
  right: 0;
  bottom: 0;
  height: 1px;
  background: linear-gradient(
    to right,
    var(--acento),
    rgba(255, 255, 255, 0.07) 42%,
    transparent 82%
  );
  opacity: 0.55;
}

.grupo-marca {
  display: grid;
  place-items: center;
  width: 38px;
  height: 38px;
  flex-shrink: 0;
  border-radius: 11px;
  font-size: 1.15rem;
  background: var(--acento);
  border: 1px solid var(--acento);
  /* El color plano detras de un emoji lo apaga; el filtro lo baja a un tinte
     y deja el glifo legible. */
  filter: saturate(0.85);
  box-shadow: inset 0 0 0 99px rgba(14, 15, 32, 0.82);
}

.grupo-texto {
  flex: 1;
  min-width: 0;
}

.grupo-texto h3 {
  margin: 0;
  font-size: 1.12rem;
  letter-spacing: -0.2px;
}

.grupo-texto p {
  margin: 2px 0 0;
  font-size: 0.78rem;
  color: var(--text-muted);
}

.grupo-cuenta {
  flex-shrink: 0;
  padding: 3px 11px;
  border-radius: 999px;
  font-size: 0.7rem;
  font-weight: 700;
  color: var(--acento);
  border: 1px solid var(--acento);
  opacity: 0.75;
}

/* ------------------------------ las tarjetas ------------------------------
   Portada arriba con el color y el patron del juego, datos abajo. La tarjeta
   entera es el boton, asi que el "Jugar X" que estaba repetido doce veces se
   fue: era una linea de ruido por tarjeta diciendo lo que ya hace el click. */

.games-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(216px, 1fr));
  gap: 14px;
}

.game-card {
  display: flex;
  flex-direction: column;
  overflow: hidden;
  border-radius: 14px;
  border: 1px solid rgba(255, 255, 255, 0.07);
  background: var(--bg-card);
  cursor: pointer;
  transition: transform 0.16s ease, border-color 0.16s ease, box-shadow 0.16s ease;
}

.game-card:hover,
.game-card:focus-visible {
  transform: translateY(-3px);
  border-color: var(--color-juego);
  box-shadow: 0 12px 28px -14px var(--color-juego);
  outline: none;
}

.portada {
  position: relative;
  display: grid;
  place-items: center;
  aspect-ratio: 16 / 11;
  overflow: hidden;
  background:
    radial-gradient(
      circle at 50% 125%,
      var(--color-juego),
      rgba(0, 0, 0, 0) 70%
    ),
    linear-gradient(165deg, rgba(255, 255, 255, 0.06), rgba(0, 0, 0, 0.3));
}

/* Los patrones son gradientes repetidos, sin un solo archivo de imagen. Cada
   juego hereda uno y, junto con su color, hace que dos tarjetas no se vean
   iguales. No reemplaza a tener ilustracion por juego: levanta el piso. */
.portada::before {
  content: '';
  position: absolute;
  inset: 0;
  /* Sin mix-blend-mode: soft-light con blanco sobre un fondo oscuro no
     levanta casi nada y el patron quedaba invisible. Blanco plano a poca
     opacidad se ve, y es lo que hace que dos portadas no sean la misma. */
  opacity: 0.22;
}

.patron-rayos::before {
  background: repeating-conic-gradient(
    from 0deg at 50% 130%,
    rgba(255, 255, 255, 0.85) 0deg 4deg,
    transparent 4deg 13deg
  );
}

.patron-puntos::before {
  background-image: radial-gradient(rgba(255, 255, 255, 0.9) 1.4px, transparent 1.5px);
  background-size: 13px 13px;
}

.patron-diagonal::before {
  background: repeating-linear-gradient(
    -45deg,
    rgba(255, 255, 255, 0.7) 0 2px,
    transparent 2px 11px
  );
}

.patron-ondas::before {
  background: repeating-radial-gradient(
    circle at 50% 108%,
    rgba(255, 255, 255, 0.75) 0 1.5px,
    transparent 1.5px 16px
  );
}

.patron-grilla::before {
  background-image:
    linear-gradient(rgba(255, 255, 255, 0.55) 1px, transparent 1px),
    linear-gradient(90deg, rgba(255, 255, 255, 0.55) 1px, transparent 1px);
  background-size: 17px 17px;
}

.portada-glifo {
  position: relative;
  font-size: 2.85rem;
  line-height: 1;
  filter: drop-shadow(0 5px 14px rgba(0, 0, 0, 0.6));
  transition: transform 0.16s ease;
}

.game-card:hover .portada-glifo {
  transform: scale(1.09);
}

.portada-cta {
  position: absolute;
  top: 8px;
  right: 8px;
  padding: 2px 9px;
  border-radius: 999px;
  font-size: 0.6rem;
  font-weight: 700;
  color: #fff;
  background: rgba(0, 0, 0, 0.5);
  border: 1px solid rgba(255, 255, 255, 0.2);
}

.game-cuerpo {
  padding: 11px 13px 13px;
}

.game-titulo {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 6px;
  margin-bottom: 5px;
}

.game-titulo h4 {
  margin: 0;
  font-size: 0.95rem;
}

.marca {
  padding: 1px 7px;
  border-radius: 999px;
  font-size: 0.58rem;
  font-weight: 700;
  letter-spacing: 0.3px;
  border: 1px solid currentColor;
}

.marca-rapida {
  color: #38bdf8;
}

.marca-pvp {
  color: #34d399;
}

.game-cuerpo p {
  margin: 0;
  color: var(--text-muted);
  font-size: 0.72rem;
  line-height: 1.42;
  /* A dos lineas: la descripcion ayuda a elegir, pero si crece empareja la
     altura de todas las tarjetas con la del texto mas largo. */
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}

@media (max-width: 760px) {
  .lobby-container {
    padding: 16px 16px 30px;
  }

  .games-grid {
    grid-template-columns: repeat(auto-fill, minmax(150px, 1fr));
    gap: 10px;
  }

  .portada-glifo {
    font-size: 2.2rem;
  }
}
</style>
