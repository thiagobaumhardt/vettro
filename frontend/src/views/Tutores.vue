<script setup>
import { onMounted, reactive, ref } from "vue";

import { tutoresApi } from "@/api/tutores";
import { toast } from "@/stores/toast";

const vazio = { id: "", nome: "", tel: "", email: "", cpf: "", endereco: "", obs: "" };
const form = reactive({ ...vazio });
const editando = ref(false);
const lista = ref([]);
const busca = ref("");

async function carregar() {
  lista.value = await tutoresApi.listar(busca.value);
}

function cancelar() {
  Object.assign(form, vazio);
  editando.value = false;
}

async function salvar() {
  if (!form.nome || !form.tel) {
    toast("Preencha nome e telefone.", false);
    return;
  }
  const dados = {
    nome: form.nome,
    tel: form.tel,
    email: form.email || null,
    cpf: form.cpf || null,
    endereco: form.endereco || null,
    obs: form.obs || null,
  };
  try {
    if (form.id) await tutoresApi.atualizar(form.id, dados);
    else await tutoresApi.criar(dados);
    toast(form.id ? "Tutor atualizado!" : "Tutor cadastrado!");
    cancelar();
    carregar();
  } catch (e) {
    toast(e.message, false);
  }
}

function editar(t) {
  Object.assign(form, { ...vazio, ...t });
  editando.value = true;
}

async function excluir(t) {
  if (!confirm("Excluir este tutor?")) return;
  try {
    await tutoresApi.excluir(t.id);
    toast("Tutor removido.");
    carregar();
  } catch (e) {
    toast(e.message, false);
  }
}

onMounted(carregar);
</script>

<template>
  <div class="tab">
    <h2>👤 Tutores</h2>

    <div class="card">
      <div class="section-title">{{ editando ? "Editar Tutor" : "Novo Tutor" }}</div>
      <div class="form-grid">
        <div><label>Nome completo *</label><input v-model="form.nome" placeholder="Ex: João Silva" /></div>
        <div><label>Telefone / WhatsApp *</label><input v-model="form.tel" placeholder="(51) 99999-0000" /></div>
        <div><label>E-mail</label><input v-model="form.email" type="email" placeholder="joao@email.com" /></div>
        <div><label>CPF</label><input v-model="form.cpf" placeholder="000.000.000-00" /></div>
        <div class="full"><label>Endereço</label><input v-model="form.endereco" placeholder="Rua, número, bairro, cidade" /></div>
        <div class="full"><label>Observações</label><textarea v-model="form.obs" placeholder="Informações adicionais..."></textarea></div>
      </div>
      <div class="form-actions">
        <button class="btn btn-primary" @click="salvar">Salvar Tutor</button>
        <button class="btn btn-secondary" @click="cancelar">Cancelar</button>
      </div>
    </div>

    <div class="card">
      <div class="section-title">Tutores Cadastrados</div>
      <div class="search-bar">
        <input v-model="busca" placeholder="Buscar por nome ou telefone..." @input="carregar" />
      </div>
      <div class="table-wrap">
        <div v-if="!lista.length" class="empty"><span class="empty-icon">👤</span>Nenhum tutor cadastrado.</div>
        <table v-else>
          <thead>
            <tr><th>Nome</th><th>Telefone</th><th>E-mail</th><th>Ações</th></tr>
          </thead>
          <tbody>
            <tr v-for="t in lista" :key="t.id">
              <td><router-link :to="`/tutores/${t.id}`" class="btn-link">{{ t.nome }}</router-link></td>
              <td>{{ t.tel }}</td>
              <td>{{ t.email || "—" }}</td>
              <td>
                <div class="td-actions">
                  <button class="btn btn-edit" @click="editar(t)">Editar</button>
                  <button class="btn btn-danger" @click="excluir(t)">Excluir</button>
                </div>
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>
  </div>
</template>
