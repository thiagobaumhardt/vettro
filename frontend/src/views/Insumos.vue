<script setup>
import { onMounted, reactive, ref } from "vue";

import { insumosApi } from "@/api/insumos";
import { toast } from "@/stores/toast";
import { fmt } from "@/utils";

const vazio = { id: "", nome: "", categoria: "", valor: "", qtd: "", obs: "" };
const form = reactive({ ...vazio });
const lista = ref([]);
const reporAberto = ref(null);
const reporQtd = ref(1);

async function carregar() {
  lista.value = await insumosApi.listar();
}

function cancelar() {
  Object.assign(form, vazio);
}

async function salvar() {
  if (!form.nome || form.valor === "") {
    toast("Preencha nome e valor.", false);
    return;
  }
  const dados = {
    nome: form.nome,
    categoria: form.categoria || null,
    valor: Number(form.valor),
    qtd: form.qtd === "" ? 0 : Number(form.qtd),
    obs: form.obs || null,
  };
  try {
    if (form.id) await insumosApi.atualizar(form.id, dados);
    else await insumosApi.criar(dados);
    toast(form.id ? "Insumo atualizado!" : "Insumo cadastrado!");
    cancelar();
    carregar();
  } catch (e) {
    toast(e.message, false);
  }
}

function editar(i) {
  Object.assign(form, { id: i.id, nome: i.nome, categoria: i.categoria || "", valor: i.valor, qtd: i.qtd, obs: i.obs || "" });
}

async function excluir(i) {
  if (!confirm("Excluir?")) return;
  await insumosApi.excluir(i.id);
  toast("Insumo removido.");
  carregar();
}

function abrirRepor(id) {
  reporAberto.value = id;
  reporQtd.value = 1;
}

async function confirmarRepor(id) {
  try {
    await insumosApi.repor(id, Number(reporQtd.value) || 1);
    toast("Estoque atualizado!");
    reporAberto.value = null;
    carregar();
  } catch (e) {
    toast(e.message, false);
  }
}

function qCls(q) {
  return q <= 0 ? "qty-warn" : q < 3 ? "qty-low" : "";
}
function qTxt(q) {
  return q <= 0 ? "⛔ Sem estoque" : q < 3 ? `⚠️ ${q} un.` : `${q} un.`;
}

onMounted(carregar);
</script>

<template>
  <div class="tab">
    <h2>📦 Insumos / Estoque</h2>
    <div class="card">
      <div class="section-title">{{ form.id ? "Editar Insumo" : "Novo Insumo" }}</div>
      <div class="form-grid">
        <div><label>Nome do Insumo *</label><input v-model="form.nome" placeholder="Ex: Seringa 5ml" /></div>
        <div>
          <label>Categoria</label>
          <select v-model="form.categoria">
            <option value="">Selecione...</option>
            <option>Medicamento</option>
            <option>Material descartável</option>
            <option>Equipamento</option>
            <option>Higiene</option>
            <option>Outro</option>
          </select>
        </div>
        <div><label>Valor Unitário (R$) *</label><input v-model="form.valor" type="number" step="0.01" min="0" placeholder="0,00" /></div>
        <div><label>Quantidade em Estoque</label><input v-model="form.qtd" type="number" min="0" placeholder="0" /></div>
        <div class="full"><label>Observações</label><textarea v-model="form.obs" placeholder="Fabricante, validade..."></textarea></div>
      </div>
      <div class="form-actions">
        <button class="btn btn-primary" @click="salvar">Salvar Insumo</button>
        <button class="btn btn-secondary" @click="cancelar">Cancelar</button>
      </div>
    </div>
    <div class="card">
      <div class="section-title">Estoque</div>
      <div class="table-wrap">
        <div v-if="!lista.length" class="empty"><span class="empty-icon">📦</span>Nenhum insumo cadastrado.</div>
        <table v-else>
          <thead><tr><th>Insumo</th><th>Categoria</th><th>Valor Unit.</th><th>Estoque</th><th>Ações</th></tr></thead>
          <tbody>
            <template v-for="i in lista" :key="i.id">
              <tr>
                <td>
                  <strong>{{ i.nome }}</strong>
                  <br v-if="i.obs" />
                  <small v-if="i.obs" style="color: #8c8a78">{{ i.obs }}</small>
                </td>
                <td><span v-if="i.categoria" class="badge b-gray">{{ i.categoria }}</span><span v-else>—</span></td>
                <td style="color: #5c6b3c; font-weight: 700">{{ fmt(i.valor) }}</td>
                <td :class="qCls(i.qtd)">{{ qTxt(i.qtd) }}</td>
                <td>
                  <div class="td-actions">
                    <button class="btn" style="background: #f0fdf4; color: #166534; border: 1px solid #bbf7d0; font-size: 0.78rem; padding: 5px 11px" @click="abrirRepor(i.id)">➕ Repor</button>
                    <button class="btn btn-edit" @click="editar(i)">Editar</button>
                    <button class="btn btn-danger" @click="excluir(i)">Excluir</button>
                  </div>
                </td>
              </tr>
              <tr v-if="reporAberto === i.id">
                <td colspan="5">
                  <div class="repor-inline-form">
                    <span class="repor-label">Adicionar ao estoque de <strong>{{ i.nome }}</strong>:</span>
                    <input v-model="reporQtd" type="number" min="1" placeholder="Qtd" />
                    <button class="btn btn-primary" style="font-size: 0.78rem; padding: 5px 14px" @click="confirmarRepor(i.id)">✔ Confirmar</button>
                    <button class="btn btn-secondary" style="font-size: 0.78rem; padding: 5px 10px" @click="reporAberto = null">✕</button>
                  </div>
                </td>
              </tr>
            </template>
          </tbody>
        </table>
      </div>
    </div>
  </div>
</template>
