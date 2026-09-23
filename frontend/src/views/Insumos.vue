<script setup>
import { nextTick, onMounted, reactive, ref } from "vue";

import { insumosApi } from "@/api/insumos";
import { confirmar } from "@/stores/confirm";
import { toast } from "@/stores/toast";
import { fmt, fmtData, hojeISO } from "@/utils";

const vazio = {
  id: "",
  nome: "",
  categoria: "",
  valor: "",
  qtd: "",
  codigo_barras: "",
  unidades_por_pacote: 1,
  data_validade: "",
  lote: "",
  obs: "",
};
const form = reactive({ ...vazio });
const lista = ref([]);
const reporAberto = ref(null);
const reporQtd = ref(1);
const reporModo = ref("pacotes"); // "pacotes" | "unidades"
const codigoScan = ref("");
const scanInput = ref(null);
const nomeInput = ref(null);
const xmlInput = ref(null);
const importando = ref(false);

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
    codigo_barras: form.codigo_barras || null,
    unidades_por_pacote: Number(form.unidades_por_pacote) || 1,
    data_validade: form.data_validade || null,
    lote: form.lote || null,
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
  Object.assign(form, {
    id: i.id,
    nome: i.nome,
    categoria: i.categoria || "",
    valor: i.valor,
    qtd: i.qtd,
    codigo_barras: i.codigo_barras || "",
    unidades_por_pacote: i.unidades_por_pacote || 1,
    data_validade: i.data_validade || "",
    lote: i.lote || "",
    obs: i.obs || "",
  });
}

async function buscarPorScanner() {
  const codigo = codigoScan.value.trim();
  codigoScan.value = "";
  if (!codigo) return;
  try {
    const insumo = await insumosApi.buscarPorCodigo(codigo);
    reporAberto.value = insumo.id;
    reporQtd.value = 1;
    reporModo.value = "pacotes";
    await nextTick();
    document.getElementById(`insumo-${insumo.id}`)?.scrollIntoView({ behavior: "smooth", block: "center" });
  } catch (e) {
    toast("Código não encontrado — preencha os dados para cadastrar este insumo.", false);
    cancelar();
    form.codigo_barras = codigo;
    await nextTick();
    nomeInput.value?.scrollIntoView({ behavior: "smooth", block: "center" });
    nomeInput.value?.focus();
  } finally {
    scanInput.value?.focus();
  }
}

async function excluir(i) {
  if (!(await confirmar("Excluir?"))) return;
  await insumosApi.excluir(i.id);
  toast("Insumo removido.");
  carregar();
}

function abrirRepor(id) {
  reporAberto.value = id;
  reporQtd.value = 1;
  reporModo.value = "pacotes";
}

function unidadesPorPacoteDe(id) {
  return lista.value.find((i) => i.id === id)?.unidades_por_pacote || 1;
}

async function confirmarRepor(id) {
  const qtd = Number(reporQtd.value) || 1;
  const unidades = reporModo.value === "pacotes" ? qtd * unidadesPorPacoteDe(id) : qtd;
  try {
    await insumosApi.repor(id, unidades);
    toast(`Estoque atualizado! (+${unidades} unidade${unidades > 1 ? "s" : ""})`);
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

function validadeInfo(dataValidade) {
  if (!dataValidade) return null;
  const dias = Math.floor((new Date(dataValidade + "T00:00:00") - new Date(hojeISO() + "T00:00:00")) / 86400000);
  if (dias < 0) return { cls: "qty-warn", texto: `⛔ Vencido em ${fmtData(dataValidade)}` };
  if (dias <= 60) return { cls: "qty-low", texto: `⚠️ Vence em ${fmtData(dataValidade)}` };
  return { cls: "", texto: `Val.: ${fmtData(dataValidade)}` };
}

async function importarXml(ev) {
  const arquivo = ev.target.files[0];
  ev.target.value = "";
  if (!arquivo) return;
  importando.value = true;
  try {
    const resultado = await insumosApi.importarXml(arquivo);
    const partes = [];
    if (resultado.criados.length) partes.push(`${resultado.criados.length} insumo(s) novo(s)`);
    if (resultado.atualizados.length) partes.push(`${resultado.atualizados.length} reposto(s)`);
    if (resultado.ignorados.length) partes.push(`${resultado.ignorados.length} ignorado(s)`);
    toast(partes.length ? `Importação concluída: ${partes.join(", ")}.` : "Nenhum item processado.");
    carregar();
  } catch (e) {
    toast(e.message, false);
  } finally {
    importando.value = false;
  }
}

onMounted(carregar);
</script>

<template>
  <div class="tab">
    <h2>📦 Insumos / Estoque</h2>
    <div class="card">
      <div class="section-title">{{ form.id ? "Editar Insumo" : "Novo Insumo" }}</div>
      <div class="form-grid">
        <div><label>Nome do Insumo *</label><input ref="nomeInput" v-model="form.nome" placeholder="Ex: Seringa 5ml" /></div>
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
        <div><label>Código de barras</label><input v-model="form.codigo_barras" placeholder="Escaneie ou digite o código" /></div>
        <div>
          <label>Unidades por pacote/caixa</label>
          <input v-model="form.unidades_por_pacote" type="number" min="1" placeholder="1" />
          <p style="font-size: 0.75rem; color: #8c8a78; margin-top: 4px">
            Se o código de barras é da caixa (ex: caixa com 100 seringas), informe 100 aqui — ao escanear, o sistema
            soma a quantidade certa automaticamente.
          </p>
        </div>
        <div><label>Data de validade</label><input v-model="form.data_validade" type="date" /></div>
        <div><label>Lote</label><input v-model="form.lote" placeholder="Ex: L2026034" /></div>
        <div class="full"><label>Observações</label><textarea v-model="form.obs" placeholder="Fabricante, condições de armazenamento..."></textarea></div>
      </div>
      <div class="form-actions">
        <button class="btn btn-primary" @click="salvar">Salvar Insumo</button>
        <button class="btn btn-secondary" @click="cancelar">Cancelar</button>
      </div>
    </div>
    <div class="card">
      <div class="section-title-row" style="margin-bottom: 12px">
        <span class="st-label">Estoque</span>
        <button class="btn btn-secondary" style="font-size: 0.78rem; padding: 6px 14px" :disabled="importando" @click="xmlInput.click()">
          {{ importando ? "Importando..." : "📤 Importar XML de compra (NF-e)" }}
        </button>
        <input ref="xmlInput" type="file" accept=".xml,text/xml" style="display: none" @change="importarXml" />
      </div>
      <p style="font-size: 0.78rem; color: #8c8a78; margin: -8px 0 14px">
        Envie o XML da nota fiscal de compra — produtos já cadastrados (pelo código de barras) têm o estoque somado
        automaticamente; produtos novos são cadastrados com nome, valor, validade e lote da nota.
      </p>
      <div class="scanner-bar">
        <span class="ic">📷</span>
        <input
          ref="scanInput"
          v-model="codigoScan"
          @keyup.enter="buscarPorScanner"
          placeholder="Escaneie o código de barras para repor estoque..."
          autofocus
        />
      </div>
      <div class="table-wrap">
        <div v-if="!lista.length" class="empty"><span class="empty-icon">📦</span>Nenhum insumo cadastrado.</div>
        <table v-else>
          <thead><tr><th>Insumo</th><th>Categoria</th><th>Valor Unit.</th><th>Estoque</th><th>Ações</th></tr></thead>
          <tbody>
            <template v-for="i in lista" :key="i.id">
              <tr :id="`insumo-${i.id}`">
                <td>
                  <strong>{{ i.nome }}</strong>
                  <br v-if="i.unidades_por_pacote > 1" />
                  <small v-if="i.unidades_por_pacote > 1" style="color: #8c8a78">📦 Pacote com {{ i.unidades_por_pacote }} un.</small>
                  <template v-if="validadeInfo(i.data_validade)">
                    <br />
                    <small :class="validadeInfo(i.data_validade).cls">{{ validadeInfo(i.data_validade).texto }}</small>
                  </template>
                  <br v-if="i.lote" />
                  <small v-if="i.lote" style="color: #8c8a78">Lote: {{ i.lote }}</small>
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
                    <select v-if="i.unidades_por_pacote > 1" v-model="reporModo" class="repor-modo">
                      <option value="pacotes">Pacotes/caixas ({{ i.unidades_por_pacote }} un. cada)</option>
                      <option value="unidades">Unidades avulsas</option>
                    </select>
                    <input v-model="reporQtd" type="number" min="1" placeholder="Qtd" />
                    <span v-if="i.unidades_por_pacote > 1 && reporModo === 'pacotes'" style="font-size: 0.78rem; color: #8c8a78">
                      = {{ (Number(reporQtd) || 0) * i.unidades_por_pacote }} unidades
                    </span>
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
