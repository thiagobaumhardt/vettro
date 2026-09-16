<script setup>
import { computed, onMounted, reactive, ref } from "vue";

import { cirurgiasApi } from "@/api/ficha";
import { insumosApi } from "@/api/insumos";
import { cirurgiasCatApi } from "@/api/servicos";
import { toast } from "@/stores/toast";
import { fmt } from "@/utils";

const props = defineProps({ paciente: Object });
const peso = computed(() => Number(props.paciente.peso) || 0);

function valorPorPeso(cat) {
  const p = peso.value;
  const vp = cat.valor_p ?? null;
  const vm = cat.valor_m ?? null;
  const vg = cat.valor_g ?? null;
  if (p > 0 && p < 10) return vp || 0;
  if (p >= 10 && p <= 25) return vm || 0;
  if (p > 25) return vg || 0;
  return vp || vm || vg || 0;
}

const faixaLabel = computed(() => {
  const p = peso.value;
  if (p <= 0) return "Sem peso cadastrado";
  if (p < 10) return `⚖️ Faixa: até 10 kg (${p} kg)`;
  if (p <= 25) return `⚖️ Faixa: 10–25 kg (${p} kg)`;
  return `⚖️ Faixa: acima de 25 kg (${p} kg)`;
});

const cirurgiasCat = ref([]);
const insumos = ref([]);
const hist = ref([]);

const vazio = () => ({
  proc: "",
  clinica: "",
  anestesista: "",
  data: "",
  hora: "",
  desc_cir: "",
  pos_op: "",
  plantao: false,
  outra_cidade: false,
});

const form = reactive(vazio());
const procSel = reactive(new Set());
const insumosSel = reactive({});

const totalProc = computed(() => cirurgiasCat.value.filter((c) => procSel.has(c.id)).reduce((acc, c) => acc + valorPorPeso(c), 0));
const totalIns = computed(() =>
  insumos.value.filter((i) => insumosSel[i.id] !== undefined).reduce((acc, i) => acc + i.valor * (insumosSel[i.id] || 1), 0)
);
const total = computed(() => {
  let t = totalProc.value + totalIns.value;
  if (form.plantao && totalProc.value > 0) t += totalProc.value * 0.5;
  if (form.outra_cidade) t += 50;
  return t;
});

function toggleProc(id) {
  procSel.has(id) ? procSel.delete(id) : procSel.add(id);
}
function toggleInsumo(id) {
  if (insumosSel[id] !== undefined) delete insumosSel[id];
  else insumosSel[id] = 1;
}

async function carregar() {
  const [c, i, h] = await Promise.all([cirurgiasCatApi.listar(), insumosApi.listar(), cirurgiasApi.listar(props.paciente.id)]);
  cirurgiasCat.value = c;
  insumos.value = i;
  hist.value = h;
}

function limpar() {
  Object.assign(form, vazio());
  procSel.clear();
  Object.keys(insumosSel).forEach((k) => delete insumosSel[k]);
}

async function salvar() {
  if (!form.proc) {
    toast("Informe o nome do procedimento.", false);
    return;
  }
  const payload = {
    ...form,
    data: form.data || null,
    hora: form.hora || null,
    cirurgia_cat_ids: [...procSel],
    insumos: Object.entries(insumosSel).map(([id, qtd]) => ({ id, qtd })),
  };
  try {
    await cirurgiasApi.criar(props.paciente.id, payload);
    toast("Cirurgia registrada!" + (payload.cirurgia_cat_ids.length || payload.insumos.length ? " Cobrança gerada automaticamente." : ""));
    limpar();
    carregar();
  } catch (e) {
    toast(e.message, false);
  }
}

async function excluir(id) {
  if (!confirm("Excluir este registro cirúrgico?")) return;
  await cirurgiasApi.excluir(id);
  toast("Registro removido.");
  carregar();
}

onMounted(carregar);
</script>

<template>
  <div class="card">
    <div class="section-title">Nova Cirurgia</div>
    <div class="form-grid">
      <div class="full"><label>Procedimento *</label><input v-model="form.proc" placeholder="Ex: Castração" /></div>
      <div><label>Data</label><input v-model="form.data" type="date" /></div>
      <div><label>Hora</label><input v-model="form.hora" type="time" /></div>
      <div><label>Clínica</label><input v-model="form.clinica" placeholder="Local do procedimento" /></div>
      <div><label>Anestesista</label><input v-model="form.anestesista" placeholder="Nome do anestesista" /></div>
      <div class="full"><label>Descrição da cirurgia</label><textarea v-model="form.desc_cir" placeholder="Detalhes do procedimento..."></textarea></div>
      <div class="full"><label>Pós-operatório</label><textarea v-model="form.pos_op" placeholder="Orientações, medicações..."></textarea></div>
    </div>

    <div style="margin-top: 16px; display: flex; gap: 20px; flex-wrap: wrap">
      <div>
        <div style="font-size: 0.78rem; font-weight: 700; color: #5c6b3c; text-transform: uppercase; letter-spacing: 0.06em; margin-bottom: 8px">Tipo de atendimento</div>
        <div class="radio-group">
          <label><input v-model="form.plantao" type="radio" :value="false" /> Normal</label>
          <label><input v-model="form.plantao" type="radio" :value="true" /> 🌙 Plantão (+50%)</label>
        </div>
      </div>
      <label style="display: flex; align-items: center; gap: 6px; font-size: 0.86rem; color: #3f3f33">
        <input v-model="form.outra_cidade" type="checkbox" style="width: 16px; height: 16px; accent-color: #6b7345" />
        📍 Deslocamento (outra cidade, +R$ 50)
      </label>
    </div>

    <div class="form-grid" style="margin-top: 16px">
      <div>
        <label>Procedimentos cirúrgicos</label>
        <div style="font-size: 0.76rem; color: #5c6b3c; font-weight: 700; margin-bottom: 6px">{{ faixaLabel }}</div>
        <div class="select-list">
          <div v-if="!cirurgiasCat.length" style="padding: 12px; color: #8c8a78; font-size: 0.85rem">Nenhum procedimento cadastrado.</div>
          <div v-for="c in cirurgiasCat" :key="c.id" class="item">
            <input type="checkbox" :checked="procSel.has(c.id)" @change="toggleProc(c.id)" />
            <span class="item-label">{{ c.nome }}</span>
            <span style="font-weight: 800; color: #5c6b3c">{{ fmt(valorPorPeso(c)) }}</span>
          </div>
        </div>
      </div>
      <div>
        <label>Insumos utilizados</label>
        <div class="select-list">
          <div v-if="!insumos.length" style="padding: 12px; color: #8c8a78; font-size: 0.85rem">Nenhum insumo cadastrado.</div>
          <div v-for="i in insumos" :key="i.id" class="item">
            <input type="checkbox" :checked="insumosSel[i.id] !== undefined" @change="toggleInsumo(i.id)" />
            <span class="item-label">{{ i.nome }} <small style="color: #8c8a78">(est: {{ i.qtd }})</small></span>
            <input v-if="insumosSel[i.id] !== undefined" class="qty-input" type="number" min="1" v-model.number="insumosSel[i.id]" />
          </div>
        </div>
      </div>
    </div>

    <div class="total-box">
      <span class="total-label">Total da cirurgia</span>
      <span class="total-value">{{ fmt(total) }}</span>
    </div>

    <div class="form-actions">
      <button class="btn btn-primary" @click="salvar">💾 Registrar Cirurgia</button>
      <button class="btn btn-secondary" @click="limpar">Limpar</button>
    </div>
  </div>

  <div class="card">
    <div class="section-title">Histórico de Cirurgias</div>
    <div v-if="!hist.length" class="empty"><span class="empty-icon">🔪</span>Nenhuma cirurgia registrada.</div>
    <details v-for="c in hist" :key="c.id" class="hist-entry">
      <summary class="hist-entry-header">
        <span class="hist-date">📅 {{ c.data }} às {{ c.hora }}</span>
        <div class="hist-tags">
          <span class="badge b-gray">{{ c.proc }}</span>
          <span v-if="c.clinica" class="badge b-blue">{{ c.clinica }}</span>
          <span v-if="c.plantao" class="badge" style="background: #fef3c7; color: #92400e">🌙 Plantão</span>
          <span v-if="c.outra_cidade" class="badge" style="background: #dbeafe; color: #1e40af">📍 Outra cidade</span>
          <span v-if="c.total > 0" class="badge b-blue" style="font-weight: 800">💰 {{ fmt(c.total) }}</span>
        </div>
      </summary>
      <div class="hist-body">
        <div class="hist-detail-grid">
          <div v-if="c.anestesista" class="hist-detail-item"><label>Anestesista</label><p>{{ c.anestesista }}</p></div>
          <div v-if="c.desc_cir" class="hist-detail-item full"><label>Descrição</label><p>{{ c.desc_cir }}</p></div>
          <div v-if="c.pos_op" class="hist-detail-item full"><label>Pós-operatório</label><p>{{ c.pos_op }}</p></div>
        </div>
        <div v-if="c.procedimentos?.length || c.insumos?.length" style="margin-top: 14px; padding-top: 12px; border-top: 1px dashed #e1dec9">
          <div v-if="c.procedimentos?.length" style="display: flex; gap: 6px; flex-wrap: wrap; margin-bottom: 8px">
            <strong style="font-size: 0.78rem; color: #3f3f33; align-self: center">Procedimentos:</strong>
            <span v-for="p in c.procedimentos" :key="p.id" class="badge b-green">{{ p.nome }} · {{ fmt(p.valor) }}</span>
          </div>
          <div v-if="c.insumos?.length" style="display: flex; gap: 6px; flex-wrap: wrap">
            <strong style="font-size: 0.78rem; color: #3f3f33; align-self: center">Insumos:</strong>
            <span v-for="i in c.insumos" :key="i.id" class="badge b-blue">{{ i.nome }} ×{{ i.qtd }} · {{ fmt(i.valor * i.qtd) }}</span>
          </div>
        </div>
        <div style="margin-top: 12px"><button class="btn btn-danger" @click="excluir(c.id)">Excluir este registro</button></div>
      </div>
    </details>
  </div>
</template>
