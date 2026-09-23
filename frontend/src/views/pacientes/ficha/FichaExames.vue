<script setup>
import { onMounted, ref } from "vue";

import { exemasApi } from "@/api/ficha";
import { confirmar } from "@/stores/confirm";
import { toast } from "@/stores/toast";

const props = defineProps({ pacienteId: String });
const lista = ref([]);
const enviando = ref(false);

async function carregar() {
  lista.value = await exemasApi.listar(props.pacienteId);
}

async function enviar(ev) {
  const files = [...ev.target.files];
  if (!files.length) return;
  enviando.value = true;
  try {
    await exemasApi.anexar(props.pacienteId, files);
    toast("Exame(s) anexado(s)!");
    carregar();
  } catch (e) {
    toast(e.message, false);
  } finally {
    enviando.value = false;
    ev.target.value = "";
  }
}

async function excluir(id) {
  if (!(await confirmar("Remover?"))) return;
  await exemasApi.excluir(id);
  toast("Exame removido.");
  carregar();
}

function tamanho(bytes) {
  return (bytes / 1024 / 1024).toFixed(2) + " MB";
}

onMounted(carregar);
</script>

<template>
  <div class="card">
    <div class="section-title">Exames (PDF)</div>
    <label class="upload-label">
      📎 {{ enviando ? "Enviando..." : "Anexar exame(s)" }}
      <input type="file" accept="application/pdf" multiple :disabled="enviando" @change="enviar" />
    </label>

    <div v-if="!lista.length" class="empty"><span class="empty-icon">📄</span>Nenhum exame anexado.</div>
    <div v-else class="pdf-list">
      <div v-for="e in lista" :key="e.id" class="pdf-item">
        <div class="pdf-icon">📄</div>
        <div class="pdf-info">
          <strong>{{ e.nome }}</strong>
          <small>{{ tamanho(e.tamanho) }}</small>
        </div>
        <a :href="e.conteudo" target="_blank" rel="noopener">Abrir</a>
        <button class="del-btn" @click="excluir(e.id)">Excluir</button>
      </div>
    </div>
  </div>
</template>
