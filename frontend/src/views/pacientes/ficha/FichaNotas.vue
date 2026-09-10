<script setup>
import { onMounted, reactive, ref } from "vue";

import { notasApi } from "@/api/ficha";
import { toast } from "@/stores/toast";

const props = defineProps({ pacienteId: String });
const lista = ref([]);
const form = reactive({ id: "", titulo: "", conteudo: "" });

async function carregar() {
  lista.value = await notasApi.listar(props.pacienteId);
}

function cancelar() {
  form.id = "";
  form.titulo = "";
  form.conteudo = "";
}

async function salvar() {
  if (!form.conteudo.trim()) {
    toast("Escreva algo na anotação.", false);
    return;
  }
  try {
    if (form.id) await notasApi.atualizar(form.id, { titulo: form.titulo || null, conteudo: form.conteudo });
    else await notasApi.criar(props.pacienteId, { titulo: form.titulo || null, conteudo: form.conteudo });
    toast(form.id ? "Anotação atualizada!" : "Anotação salva!");
    cancelar();
    carregar();
  } catch (e) {
    toast(e.message, false);
  }
}

function editar(n) {
  form.id = n.id;
  form.titulo = n.titulo || "";
  form.conteudo = n.conteudo;
}

async function excluir(id) {
  if (!confirm("Excluir esta anotação?")) return;
  await notasApi.excluir(id);
  toast("Anotação removida.");
  carregar();
}

onMounted(carregar);
</script>

<template>
  <div class="card">
    <div class="section-title">{{ form.id ? "Editar Anotação" : "Nova Anotação" }}</div>
    <div class="form-grid">
      <div class="full"><label>Título</label><input v-model="form.titulo" placeholder="Opcional" /></div>
      <div class="full"><label>Conteúdo</label><textarea v-model="form.conteudo" placeholder="Escreva sua anotação..." style="min-height: 100px"></textarea></div>
    </div>
    <div class="form-actions">
      <button class="btn btn-primary" @click="salvar">Salvar Anotação</button>
      <button v-if="form.id" class="btn btn-secondary" @click="cancelar">Cancelar</button>
    </div>
  </div>

  <div v-if="!lista.length" class="empty"><span class="empty-icon">📝</span>Nenhuma anotação registrada.</div>
  <div v-for="n in lista" :key="n.id" class="nota-card">
    <div class="nota-header">
      <div class="nota-titulo">{{ n.titulo || "Sem título" }}</div>
      <div class="nota-data">{{ new Date(n.criado_em).toLocaleString("pt-BR") }}</div>
    </div>
    <div class="nota-conteudo">{{ n.conteudo }}</div>
    <div class="nota-actions">
      <button class="btn btn-edit" @click="editar(n)">Editar</button>
      <button class="btn btn-danger" @click="excluir(n.id)">Excluir</button>
    </div>
  </div>
</template>
