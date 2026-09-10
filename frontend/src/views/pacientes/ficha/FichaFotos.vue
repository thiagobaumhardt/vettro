<script setup>
import { onMounted, ref } from "vue";

import { fotosApi } from "@/api/ficha";
import { toast } from "@/stores/toast";

const props = defineProps({ pacienteId: String });
const lista = ref([]);
const enviando = ref(false);
const lightbox = ref(null);

async function carregar() {
  lista.value = await fotosApi.listar(props.pacienteId);
}

async function enviar(ev) {
  const files = [...ev.target.files];
  if (!files.length) return;
  enviando.value = true;
  try {
    await fotosApi.anexar(props.pacienteId, files);
    toast("Foto(s) adicionada(s)!");
    carregar();
  } catch (e) {
    toast(e.message, false);
  } finally {
    enviando.value = false;
    ev.target.value = "";
  }
}

async function excluir(id) {
  if (!confirm("Remover?")) return;
  await fotosApi.excluir(id);
  toast("Foto removida.");
  carregar();
}

onMounted(carregar);
</script>

<template>
  <div class="card">
    <div class="section-title">Fotos</div>
    <label class="upload-label">
      📷 {{ enviando ? "Enviando..." : "Adicionar foto(s)" }}
      <input type="file" accept="image/*" multiple :disabled="enviando" @change="enviar" />
    </label>

    <div v-if="!lista.length" class="empty"><span class="empty-icon">🖼️</span>Nenhuma foto adicionada.</div>
    <div v-else class="foto-grid">
      <div v-for="f in lista" :key="f.id" class="foto-item">
        <img :src="f.conteudo" :title="f.nome" @click="lightbox = f.conteudo" />
        <button class="del-btn" @click="excluir(f.id)">✕</button>
      </div>
    </div>

    <div v-if="lightbox" id="lightbox" class="open" @click="lightbox = null">
      <span class="lb-close" @click="lightbox = null">✕</span>
      <img :src="lightbox" />
    </div>
  </div>
</template>
