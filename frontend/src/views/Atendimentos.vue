<script setup>
import { computed, onMounted, reactive, ref } from "vue";

import { atendimentosApi } from "@/api/atendimentos";
import { insumosApi } from "@/api/insumos";
import { pacientesApi } from "@/api/pacientes";
import { servicosApi } from "@/api/servicos";
import { toast } from "@/stores/toast";
import { especieEmoji, fmt, hojeISO } from "@/utils";

const pacientes = ref([]);
const servicos = ref([]);
const insumos = ref([]);
const lista = ref([]);

const form = reactive({ pacienteId: "", data: hojeISO(), hora: "", obs: "", plantao: false });
const servicosSel = reactive(new Set());
const insumosSel = reactive({});

const pacienteSelecionado = computed(() => pacientes.value.find((p) => p.id === form.pacienteId));

const totalServ = computed(() => servicos.value.filter((s) => servicosSel.has(s.id)).reduce((acc, s) => acc + s.valor, 0));
const totalIns = computed(() =>
  insumos.value.filter((i) => insumosSel[i.id] !== undefined).reduce((acc, i) => acc + i.valor * (insumosSel[i.id] || 1), 0)
);
const total = computed(() => totalServ.value + totalIns.value + (form.plantao && totalServ.value > 0 ? totalServ.value * 0.5 : 0));

function toggleServico(id) {
  servicosSel.has(id) ? servicosSel.delete(id) : servicosSel.add(id);
}
function toggleInsumo(id) {
  if (insumosSel[id] !== undefined) delete insumosSel[id];
  else insumosSel[id] = 1;
}

async function carregar() {
  const [p, s, i, a] = await Promise.all([pacientesApi.listar(), servicosApi.listar(), insumosApi.listar(), atendimentosApi.listar()]);
  pacientes.value = p;
  servicos.value = s;
  insumos.value = i;
  lista.value = a;
}

function limpar() {
  form.pacienteId = "";
  form.data = hojeISO();
  form.hora = "";
  form.obs = "";
  form.plantao = false;
  servicosSel.clear();
  Object.keys(insumosSel).forEach((k) => delete insumosSel[k]);
}

async function salvar() {
  if (!form.pacienteId || !form.data) {
    toast("Selecione paciente e data.", false);
    return;
  }
  const payload = {
    paciente_id: form.pacienteId,
    data: form.data,
    hora: form.hora || null,
    servico_ids: [...servicosSel],
    insumos: Object.entries(insumosSel).map(([id, qtd]) => ({ id, qtd })),
    plantao: form.plantao,
    obs: form.obs || null,
  };
  try {
    await atendimentosApi.criar(payload);
    toast("Atendimento registrado!");
    limpar();
    carregar();
  } catch (e) {
    toast(e.message, false);
  }
}

async function excluir(id) {
  if (!confirm("Excluir?")) return;
  await atendimentosApi.excluir(id);
  toast("Atendimento removido.");
  carregar();
}

onMounted(carregar);
</script>

<template>
  <div class="tab">
    <h2>📋 Atendimentos</h2>
    <div class="card">
      <div class="section-title">Registrar Atendimento</div>
      <div class="form-grid">
        <div>
          <label>Paciente *</label>
          <select v-model="form.pacienteId">
            <option value="">Selecione...</option>
            <option v-for="p in pacientes" :key="p.id" :value="p.id">{{ p.nome }}{{ p.tutor ? " (" + p.tutor.nome + ")" : "" }}</option>
          </select>
        </div>
        <div><label>Tutor</label><input :value="pacienteSelecionado?.tutor ? pacienteSelecionado.tutor.nome + ' — ' + pacienteSelecionado.tutor.tel : ''" readonly /></div>
        <div><label>Data *</label><input v-model="form.data" type="date" /></div>
        <div><label>Hora</label><input v-model="form.hora" type="time" /></div>
        <div class="full">
          <div class="radio-group">
            <label><input v-model="form.plantao" type="radio" :value="false" /> Normal</label>
            <label><input v-model="form.plantao" type="radio" :value="true" /> 🌙 Plantão (+50% nos serviços)</label>
          </div>
        </div>
        <div>
          <label>Serviços realizados</label>
          <div class="select-list">
            <div v-if="!servicos.length" style="padding: 12px; color: #a0aec0; font-size: 0.85rem">Nenhum serviço cadastrado.</div>
            <div v-for="s in servicos" :key="s.id" class="item">
              <input type="checkbox" :checked="servicosSel.has(s.id)" @change="toggleServico(s.id)" />
              <span class="item-label">{{ s.nome }}</span>
              <span style="font-weight: 700; color: #2c1a30">{{ fmt(s.valor) }}</span>
            </div>
          </div>
        </div>
        <div>
          <label>Insumos utilizados</label>
          <div class="select-list">
            <div v-if="!insumos.length" style="padding: 12px; color: #a0aec0; font-size: 0.85rem">Nenhum insumo cadastrado.</div>
            <div v-for="i in insumos" :key="i.id" class="item">
              <input type="checkbox" :checked="insumosSel[i.id] !== undefined" @change="toggleInsumo(i.id)" />
              <span class="item-label">{{ i.nome }} <small style="color: #a0aec0">(est: {{ i.qtd }})</small></span>
              <input v-if="insumosSel[i.id] !== undefined" class="qty-input" type="number" min="1" v-model.number="insumosSel[i.id]" />
            </div>
          </div>
        </div>
        <div class="full"><label>Observações</label><textarea v-model="form.obs" placeholder="Observações do atendimento..."></textarea></div>
      </div>

      <div class="total-box">
        <span class="total-label">Valor total do atendimento</span>
        <span class="total-value">{{ fmt(total) }}</span>
      </div>

      <div class="form-actions">
        <button class="btn btn-primary" @click="salvar">Registrar Atendimento</button>
        <button class="btn btn-secondary" @click="limpar">Limpar</button>
      </div>
    </div>

    <div class="card">
      <div class="section-title">Atendimentos Registrados</div>
      <div v-if="!lista.length" class="empty"><span class="empty-icon">📋</span>Nenhum atendimento registrado.</div>
      <div v-for="a in lista" :key="a.id" class="atend-card">
        <div class="atend-header">
          <div>
            <h4>
              {{ especieEmoji(a.pac_especie) }} {{ a.pac_nome }}
              <span style="font-weight: 400; color: #718096">({{ a.pac_especie }})</span>
              <span v-if="a.plantao" class="badge" style="background: #fef3c7; color: #92400e; font-size: 0.72rem">🌙 Plantão</span>
            </h4>
            <div class="meta">Tutor: {{ a.tutor_nome || "—" }}{{ a.tutor_tel ? " · " + a.tutor_tel : "" }}</div>
            <div class="meta">{{ a.data }}{{ a.hora ? " às " + a.hora : "" }}</div>
          </div>
          <div style="display: flex; gap: 6px; align-items: flex-start">
            <span style="font-size: 1.05rem; font-weight: 800; color: #2c1a30">{{ fmt(a.total) }}</span>
            <button class="btn btn-danger" @click="excluir(a.id)">Excluir</button>
          </div>
        </div>
        <div v-if="a.servicos.length" class="tags">
          <strong style="font-size: 0.78rem; color: #4a5568">Serviços:</strong>
          <span v-for="s in a.servicos" :key="s.id" class="badge b-green">{{ s.nome }} · {{ fmt(s.valor) }}</span>
        </div>
        <div v-if="a.insumos.length" class="tags">
          <strong style="font-size: 0.78rem; color: #4a5568">Insumos:</strong>
          <span v-for="i in a.insumos" :key="i.id" class="badge b-blue">{{ i.nome }} ×{{ i.qtd }} · {{ fmt(i.valor * i.qtd) }}</span>
        </div>
        <div v-if="a.obs" style="font-size: 0.84rem; color: #718096; margin-top: 6px">📝 {{ a.obs }}</div>
      </div>
    </div>
  </div>
</template>
