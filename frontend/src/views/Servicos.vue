<script setup>
import { onMounted, reactive, ref } from "vue";

import { cirurgiasCatApi, servicosApi } from "@/api/servicos";
import { confirmar } from "@/stores/confirm";
import { toast } from "@/stores/toast";
import { fmt } from "@/utils";

const servForm = reactive({ id: "", nome: "", valor: "", descricao: "" });
const servicos = ref([]);

const catForm = reactive({ id: "", nome: "", valor_p: "", valor_m: "", valor_g: "", descricao: "" });
const cirurgiasCat = ref([]);

async function carregar() {
  servicos.value = await servicosApi.listar();
  cirurgiasCat.value = await cirurgiasCatApi.listar();
}

function cancelarServico() {
  Object.assign(servForm, { id: "", nome: "", valor: "", descricao: "" });
}

async function salvarServico() {
  if (!servForm.nome || !servForm.valor) {
    toast("Preencha nome e valor.", false);
    return;
  }
  const dados = { nome: servForm.nome, valor: Number(servForm.valor), descricao: servForm.descricao || null };
  try {
    if (servForm.id) await servicosApi.atualizar(servForm.id, dados);
    else await servicosApi.criar(dados);
    toast(servForm.id ? "Serviço atualizado!" : "Serviço cadastrado!");
    cancelarServico();
    carregar();
  } catch (e) {
    toast(e.message, false);
  }
}

function editarServico(s) {
  Object.assign(servForm, { id: s.id, nome: s.nome, valor: s.valor, descricao: s.descricao || "" });
}

async function excluirServico(s) {
  if (!(await confirmar("Excluir?"))) return;
  await servicosApi.excluir(s.id);
  toast("Serviço removido.");
  carregar();
}

function cancelarCat() {
  Object.assign(catForm, { id: "", nome: "", valor_p: "", valor_m: "", valor_g: "", descricao: "" });
}

async function salvarCat() {
  if (!catForm.nome) {
    toast("Informe o nome do procedimento.", false);
    return;
  }
  if (!catForm.valor_p && !catForm.valor_m && !catForm.valor_g) {
    toast("Informe pelo menos um valor por faixa de peso.", false);
    return;
  }
  const dados = {
    nome: catForm.nome,
    valor_p: catForm.valor_p === "" ? null : Number(catForm.valor_p),
    valor_m: catForm.valor_m === "" ? null : Number(catForm.valor_m),
    valor_g: catForm.valor_g === "" ? null : Number(catForm.valor_g),
    descricao: catForm.descricao || null,
  };
  try {
    if (catForm.id) await cirurgiasCatApi.atualizar(catForm.id, dados);
    else await cirurgiasCatApi.criar(dados);
    toast(catForm.id ? "Procedimento atualizado!" : "Procedimento cadastrado!");
    cancelarCat();
    carregar();
  } catch (e) {
    toast(e.message, false);
  }
}

function editarCat(c) {
  Object.assign(catForm, {
    id: c.id,
    nome: c.nome,
    valor_p: c.valor_p ?? "",
    valor_m: c.valor_m ?? "",
    valor_g: c.valor_g ?? "",
    descricao: c.descricao || "",
  });
}

async function excluirCat(c) {
  if (!(await confirmar("Excluir?"))) return;
  await cirurgiasCatApi.excluir(c.id);
  toast("Procedimento removido.");
  carregar();
}

onMounted(carregar);
</script>

<template>
  <div class="tab">
    <h2>💉 Serviços</h2>
    <div class="card">
      <div class="section-title">{{ servForm.id ? "Editar Serviço" : "Novo Serviço" }}</div>
      <div class="form-grid">
        <div><label>Nome do Serviço *</label><input v-model="servForm.nome" placeholder="Ex: Consulta domiciliar" /></div>
        <div><label>Valor (R$) *</label><input v-model="servForm.valor" type="number" step="0.01" min="0" placeholder="0,00" /></div>
        <div class="full"><label>Descrição</label><textarea v-model="servForm.descricao" placeholder="Descreva o serviço..."></textarea></div>
      </div>
      <div class="form-actions">
        <button class="btn btn-primary" @click="salvarServico">Salvar Serviço</button>
        <button class="btn btn-secondary" @click="cancelarServico">Cancelar</button>
      </div>
    </div>
    <div class="card">
      <div class="section-title">Serviços Cadastrados</div>
      <div class="table-wrap">
        <div v-if="!servicos.length" class="empty"><span class="empty-icon">💉</span>Nenhum serviço cadastrado.</div>
        <table v-else>
          <thead><tr><th>Nome</th><th>Valor</th><th>Ações</th></tr></thead>
          <tbody>
            <tr v-for="s in servicos" :key="s.id">
              <td>{{ s.nome }}</td>
              <td style="color: #5c6b3c; font-weight: 700">{{ fmt(s.valor) }}</td>
              <td>
                <div class="td-actions">
                  <button class="btn btn-edit" @click="editarServico(s)">Editar</button>
                  <button class="btn btn-danger" @click="excluirServico(s)">Excluir</button>
                </div>
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>

    <h2 style="margin-top: 28px">🔪 Procedimentos Cirúrgicos</h2>
    <div class="card">
      <div class="section-title">{{ catForm.id ? "Editar Procedimento" : "Novo Procedimento Cirúrgico" }}</div>
      <div class="form-grid">
        <div class="full"><label>Nome do Procedimento *</label><input v-model="catForm.nome" placeholder="Ex: Castração, Mastectomia, OSH..." /></div>
        <div><label>⚖️ Valor — até 10 kg (R$)</label><input v-model="catForm.valor_p" type="number" step="0.01" min="0" placeholder="0,00" /></div>
        <div><label>⚖️ Valor — 10 a 25 kg (R$)</label><input v-model="catForm.valor_m" type="number" step="0.01" min="0" placeholder="0,00" /></div>
        <div><label>⚖️ Valor — acima de 25 kg (R$)</label><input v-model="catForm.valor_g" type="number" step="0.01" min="0" placeholder="0,00" /></div>
        <div class="full"><label>Descrição</label><textarea v-model="catForm.descricao" placeholder="Descreva o procedimento..."></textarea></div>
      </div>
      <div class="form-actions">
        <button class="btn btn-primary" @click="salvarCat">Salvar Procedimento</button>
        <button class="btn btn-secondary" @click="cancelarCat">Cancelar</button>
      </div>
    </div>
    <div class="card">
      <div class="section-title">Procedimentos Cirúrgicos Cadastrados</div>
      <div class="table-wrap">
        <div v-if="!cirurgiasCat.length" class="empty"><span class="empty-icon">🔪</span>Nenhum procedimento cadastrado.</div>
        <table v-else>
          <thead><tr><th>Nome</th><th>Até 10kg</th><th>10–25kg</th><th>Acima 25kg</th><th>Ações</th></tr></thead>
          <tbody>
            <tr v-for="c in cirurgiasCat" :key="c.id">
              <td>{{ c.nome }}</td>
              <td>{{ c.valor_p != null ? fmt(c.valor_p) : "—" }}</td>
              <td>{{ c.valor_m != null ? fmt(c.valor_m) : "—" }}</td>
              <td>{{ c.valor_g != null ? fmt(c.valor_g) : "—" }}</td>
              <td>
                <div class="td-actions">
                  <button class="btn btn-edit" @click="editarCat(c)">Editar</button>
                  <button class="btn btn-danger" @click="excluirCat(c)">Excluir</button>
                </div>
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>
  </div>
</template>
