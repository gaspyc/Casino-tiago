<template>
  <section class="fairness-panel">
    <header class="fp-head">
      <span class="fp-title">🔒 Provably fair</span>
      <button
        v-if="canRotate"
        class="fp-rotate"
        :disabled="rotating"
        @click="$emit('rotate')"
      >
        {{ rotating ? 'Revelando…' : 'Revelar y rotar' }}
      </button>
    </header>

    <p class="fp-help">{{ helpText }}</p>

    <dl class="fp-rows">
      <div class="fp-row">
        <dt>Compromiso SHA-256</dt>
        <dd>
          <code :title="serverSeedHash || ''">{{ acortar(serverSeedHash) }}</code>
          <button v-if="serverSeedHash" class="fp-copy" title="Copiar" @click="copiar(serverSeedHash)">⧉</button>
        </dd>
      </div>

      <div class="fp-row">
        <dt>Client seed</dt>
        <dd>
          <code :title="clientSeed || ''">{{ acortar(clientSeed, 18) }}</code>
          <button v-if="clientSeed" class="fp-copy" title="Copiar" @click="copiar(clientSeed)">⧉</button>
        </dd>
      </div>

      <div class="fp-row">
        <dt>{{ nonceLabel }}</dt>
        <dd><code>{{ nonce === null || nonce === undefined ? '—' : nonce }}</code></dd>
      </div>

      <div v-if="serverSeed" class="fp-row revelada">
        <dt>Server seed revelado</dt>
        <dd>
          <code :title="serverSeed">{{ acortar(serverSeed) }}</code>
          <button class="fp-copy" title="Copiar" @click="copiar(serverSeed)">⧉</button>
        </dd>
      </div>
    </dl>

    <p class="fp-formula"><code>{{ formula }}</code></p>
    <p v-if="copiado" class="fp-copiado">Copiado</p>
  </section>
</template>

<script setup>
import { ref } from 'vue';

defineProps({
  // Hash del server seed. Se publica antes de jugar; es el compromiso.
  serverSeedHash: { type: String, default: null },
  clientSeed: { type: String, default: null },
  nonce: { type: Number, default: null },
  // Sólo llega cuando la jugada terminó (Crash) o se rotó la semilla (Plinko).
  serverSeed: { type: String, default: null },
  canRotate: { type: Boolean, default: false },
  rotating: { type: Boolean, default: false },
  nonceLabel: { type: String, default: 'Jugada nº' },
  helpText: { type: String, default: '' },
  formula: { type: String, default: '' },
});

defineEmits(['rotate']);

const copiado = ref(false);

const acortar = (valor, visibles = 10) => {
  if (!valor) return '—';
  if (valor.length <= visibles * 2) return valor;
  return `${valor.slice(0, visibles)}…${valor.slice(-6)}`;
};

const copiar = async (valor) => {
  try {
    await navigator.clipboard.writeText(valor);
    copiado.value = true;
    setTimeout(() => { copiado.value = false; }, 1500);
  } catch {
    // Sin permiso de portapapeles no pasa nada: el valor completo está en el title.
  }
};
</script>

<style scoped>
.fairness-panel {
  border: 1px solid rgba(255, 255, 255, 0.1);
  border-radius: 12px;
  padding: 12px 14px;
  background: rgba(0, 0, 0, 0.22);
  font-size: 0.78rem;
}

.fp-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  margin-bottom: 6px;
}

.fp-title {
  font-weight: 700;
  letter-spacing: 0.02em;
}

.fp-rotate {
  background: transparent;
  color: var(--text-main);
  border: 1px solid rgba(255, 255, 255, 0.25);
  border-radius: 8px;
  padding: 3px 9px;
  font-size: 0.72rem;
  cursor: pointer;
}

.fp-rotate:hover:not(:disabled) {
  border-color: var(--primary);
  color: var(--primary);
}

.fp-rotate:disabled {
  opacity: 0.5;
  cursor: default;
}

.fp-help {
  margin: 0 0 10px;
  color: var(--text-muted);
  line-height: 1.4;
}

.fp-rows {
  margin: 0;
  display: grid;
  gap: 6px;
}

.fp-row {
  display: flex;
  flex-direction: column;
  align-items: flex-start;
  gap: 1px;
}

.fp-row dt {
  color: var(--text-muted);
  white-space: nowrap;
}

.fp-row dd {
  margin: 0;
  display: flex;
  align-items: center;
  gap: 4px;
  min-width: 0;
}

.fp-row code {
  font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
  font-size: 0.72rem;
  overflow-wrap: anywhere;
}

.fp-row.revelada code {
  color: var(--accent-green);
}

.fp-copy {
  background: transparent;
  border: none;
  color: var(--text-muted);
  cursor: pointer;
  padding: 0 2px;
  font-size: 0.8rem;
  line-height: 1;
}

.fp-copy:hover {
  color: var(--primary);
}

.fp-formula {
  margin: 10px 0 0;
  padding-top: 8px;
  border-top: 1px solid rgba(255, 255, 255, 0.08);
  color: var(--text-muted);
}

.fp-formula code {
  font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
  font-size: 0.68rem;
  overflow-wrap: anywhere;
}

.fp-copiado {
  margin: 6px 0 0;
  color: var(--accent-green);
  font-size: 0.7rem;
}
</style>
