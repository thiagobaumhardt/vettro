<script setup>
import { computed, onMounted, reactive, ref } from "vue";

import { anamneseApi } from "@/api/ficha";
import { insumosApi } from "@/api/insumos";
import { servicosApi } from "@/api/servicos";
import { toast } from "@/stores/toast";
import { fmt } from "@/utils";

const props = defineProps({ paciente: Object });

const servicos = ref([]);
const insumos = ref([]);
const hist = ref([]);

const vazio = () => ({
  queixa: "",
  historico: "",
  medicamentos: "",
  alergias: "",
  obs_add: "",
  alimentacao: "",
  vacina: "Desconhecido",
  verme: "Desconhecido",
  rua: "Não",
  convive: "Não",
  av_fc: "",
  av_fr: "",
  av_pa: "",
  av_temp: "",
  av_hidratacao: "",
  av_mucosas: "",
  av_linf_sub: "",
  av_linf_sube: "",
  av_linf_ing: "",
  av_linf_pop: "",
  av_demais: "",
  plantao: false,
});

const form = reactive(vazio());
const servicosSel = reactive(new Set());
const insumosSel = reactive({}); // id -> qtd

const totalServ = computed(() =>
  servicos.value.filter((s) => servicosSel.has(s.id)).reduce((acc, s) => acc + s.valor, 0)
);
const totalIns = computed(() =>
  insumos.value
    .filter((i) => insumosSel[i.id] !== undefined)
    .reduce((acc, i) => acc + i.valor * (insumosSel[i.id] || 1), 0)
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
  const [s, i, h] = await Promise.all([
    servicosApi.listar(),
    insumosApi.listar(),
    anamneseApi.listar(props.paciente.id),
  ]);
  servicos.value = s;
  insumos.value = i;
  hist.value = h;
}

function limpar() {
  Object.assign(form, vazio());
  servicosSel.clear();
  Object.keys(insumosSel).forEach((k) => delete insumosSel[k]);
}

async function salvar() {
  const payload = {
    ...form,
    servico_ids: [...servicosSel],
    insumos: Object.entries(insumosSel).map(([id, qtd]) => ({ id, qtd })),
  };
  try {
    await anamneseApi.criar(props.paciente.id, payload);
    toast("Atendimento registrado!" + (payload.servico_ids.length || payload.insumos.length ? " Cobrança gerada automaticamente." : ""));
    limpar();
    carregar();
  } catch (e) {
    toast(e.message, false);
  }
}

async function excluir(id) {
  if (!confirm("Excluir este registro de atendimento?")) return;
  await anamneseApi.excluir(id);
  toast("Registro removido.");
  carregar();
}

onMounted(carregar);
</script>

<template>
  <div class="card">
    <div class="section-title">Novo Registro de Atendimento</div>
    <div class="anamnese-grid">
      <div class="full"><label>Queixa principal / Motivo da consulta</label><textarea v-model="form.queixa" placeholder="Descreva o motivo..."></textarea></div>
      <div class="full"><label>Histórico clínico anterior</label><textarea v-model="form.historico" placeholder="Doenças, cirurgias, internações..."></textarea></div>
      <div class="full"><label>Medicamentos em uso</label><textarea v-model="form.medicamentos" placeholder="Nome, dose, frequência..."></textarea></div>
      <div>
        <label>Vacinação</label>
        <div class="radio-group">
          <label><input v-model="form.vacina" type="radio" value="Em dia" /> Em dia</label>
          <label><input v-model="form.vacina" type="radio" value="Atrasada" /> Atrasada</label>
          <label><input v-model="form.vacina" type="radio" value="Não vacinado" /> Não vacinado</label>
          <label><input v-model="form.vacina" type="radio" value="Desconhecido" /> Desconhecido</label>
        </div>
      </div>
      <div>
        <label>Vermifugação</label>
        <div class="radio-group">
          <label><input v-model="form.verme" type="radio" value="Em dia" /> Em dia</label>
          <label><input v-model="form.verme" type="radio" value="Atrasada" /> Atrasada</label>
          <label><input v-model="form.verme" type="radio" value="Não realizada" /> Não realizada</label>
          <label><input v-model="form.verme" type="radio" value="Desconhecido" /> Desconhecido</label>
        </div>
      </div>
      <div>
        <label>Alimentação</label>
        <select v-model="form.alimentacao">
          <option value="">Selecione...</option>
          <option>Ração seca</option>
          <option>Ração úmida</option>
          <option>Ração seca + úmida</option>
          <option>Comida natural</option>
          <option>Misto</option>
          <option>Outro</option>
        </select>
      </div>
      <div>
        <label>Acesso à rua</label>
        <div class="radio-group">
          <label><input v-model="form.rua" type="radio" value="Sim" /> Sim</label>
          <label><input v-model="form.rua" type="radio" value="Não" /> Não</label>
          <label><input v-model="form.rua" type="radio" value="Controlado" /> Controlado</label>
        </div>
      </div>
      <div>
        <label>Convive com outros animais</label>
        <div class="radio-group">
          <label><input v-model="form.convive" type="radio" value="Sim" /> Sim</label>
          <label><input v-model="form.convive" type="radio" value="Não" /> Não</label>
        </div>
      </div>
      <div class="full"><label>Alergias conhecidas</label><input v-model="form.alergias" placeholder="Ex: dipirona, pulgas..." /></div>
      <div class="full"><label>Observações adicionais</label><textarea v-model="form.obs_add" placeholder="Outras informações relevantes..."></textarea></div>
    </div>

    <div class="aval-section-title">🔬 Avaliação Física</div>
    <div class="aval-row"><span class="aval-icon">💓</span><span class="aval-label">FC</span><div class="aval-input"><input v-model="form.av_fc" placeholder="Ex: 80" /></div><span class="aval-unit">bpm</span></div>
    <div class="aval-row"><span class="aval-icon">🫁</span><span class="aval-label">FR</span><div class="aval-input"><input v-model="form.av_fr" placeholder="Ex: 20" /></div><span class="aval-unit">mpm</span></div>
    <div class="aval-row"><span class="aval-icon">🩺</span><span class="aval-label">PA</span><div class="aval-input"><input v-model="form.av_pa" placeholder="Ex: 120/80" /></div><span class="aval-unit">mmHg</span></div>
    <div class="aval-row"><span class="aval-icon">🌡️</span><span class="aval-label">T°C</span><div class="aval-input"><input v-model="form.av_temp" placeholder="Ex: 38.5" /></div><span class="aval-unit">°C</span></div>
    <div class="aval-row"><span class="aval-icon">💧</span><span class="aval-label">Hidratação</span><div class="aval-input"><input v-model="form.av_hidratacao" placeholder="Ex: Normal, 5%, 10%..." /></div></div>
    <div class="aval-row"><span class="aval-icon">👄</span><span class="aval-label">Mucosas</span><div class="aval-input"><input v-model="form.av_mucosas" placeholder="Ex: Rosadas, pálidas, ictéricas..." /></div></div>
    <div class="aval-row" style="flex-direction: column; align-items: flex-start">
      <div style="display: flex; align-items: center; gap: 12px; margin-bottom: 8px">
        <span class="aval-icon">🔵</span><span class="aval-label" style="width: auto">Linfonodos</span>
      </div>
      <div class="linf-grid" style="width: 100%">
        <div class="linf-item"><label>Submandibulares</label><input v-model="form.av_linf_sub" placeholder="Ex: Normal" /></div>
        <div class="linf-item"><label>Subescapulares</label><input v-model="form.av_linf_sube" placeholder="Ex: Normal" /></div>
        <div class="linf-item"><label>Inguinais</label><input v-model="form.av_linf_ing" placeholder="Ex: Normal" /></div>
        <div class="linf-item"><label>Poplíteos</label><input v-model="form.av_linf_pop" placeholder="Ex: Normal" /></div>
      </div>
    </div>
    <div class="aval-row" style="align-items: flex-start">
      <span class="aval-icon" style="padding-top: 6px">📝</span>
      <span class="aval-label" style="padding-top: 6px">Demais Informações</span>
      <div class="aval-input"><textarea v-model="form.av_demais" placeholder="Outras observações do exame físico..." style="min-height: 70px"></textarea></div>
    </div>

    <div class="aval-section-title" style="margin-top: 20px">🧾 O que foi feito / utilizado</div>
    <div style="background: #faf0f8; border: 1.5px solid #edd5e5; border-radius: 9px; padding: 12px 16px; margin-bottom: 14px">
      <div style="font-size: 0.78rem; font-weight: 700; color: #8b5e9a; text-transform: uppercase; letter-spacing: 0.06em; margin-bottom: 8px">Tipo de atendimento</div>
      <div class="radio-group">
        <label><input v-model="form.plantao" type="radio" :value="false" /> Normal</label>
        <label><input v-model="form.plantao" type="radio" :value="true" /> 🌙 Plantão <span style="font-size: 0.82rem; color: #8b5e9a; font-weight: 600">(+50% nos serviços)</span></label>
      </div>
    </div>

    <div class="form-grid">
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
            <input
              v-if="insumosSel[i.id] !== undefined"
              class="qty-input"
              type="number"
              min="1"
              v-model.number="insumosSel[i.id]"
            />
          </div>
        </div>
      </div>
    </div>

    <div class="total-box">
      <span class="total-label">Total do atendimento</span>
      <span class="total-value">{{ fmt(total) }}</span>
    </div>

    <div class="form-actions">
      <button class="btn btn-primary" @click="salvar">💾 Registrar Atendimento</button>
      <button class="btn btn-secondary" @click="limpar">Limpar</button>
    </div>
  </div>

  <div class="card">
    <div class="section-title">Histórico de Atendimentos</div>
    <div v-if="!hist.length" class="empty"><span class="empty-icon">🩺</span>Nenhum atendimento registrado ainda.</div>
    <details v-for="a in hist" :key="a.id" class="hist-entry">
      <summary class="hist-entry-header">
        <span class="hist-date">📅 {{ a.data }} às {{ a.hora }}</span>
        <div class="hist-tags">
          <span v-if="a.plantao" class="badge" style="background: #fef3c7; color: #92400e">🌙 Plantão</span>
          <span v-if="a.total > 0" class="badge b-blue" style="font-weight: 800">💰 {{ fmt(a.total) }}</span>
        </div>
      </summary>
      <div class="hist-body">
        <div class="hist-detail-grid">
          <div v-if="a.queixa" class="hist-detail-item full"><label>Queixa / Motivo</label><p>{{ a.queixa }}</p></div>
          <div v-if="a.historico" class="hist-detail-item full"><label>Histórico Clínico</label><p>{{ a.historico }}</p></div>
          <div v-if="a.medicamentos" class="hist-detail-item full"><label>Medicamentos em uso</label><p>{{ a.medicamentos }}</p></div>
          <div v-if="a.alergias" class="hist-detail-item"><label>Alergias</label><p>{{ a.alergias }}</p></div>
        </div>
        <div v-if="a.servicos?.length || a.insumos?.length" style="margin-top: 14px; padding-top: 12px; border-top: 1px dashed #e8d0eb">
          <div v-if="a.servicos?.length" style="display: flex; gap: 6px; flex-wrap: wrap; margin-bottom: 8px">
            <strong style="font-size: 0.78rem; color: #4a5568; align-self: center">Serviços:</strong>
            <span v-for="s in a.servicos" :key="s.id" class="badge b-green">{{ s.nome }} · {{ fmt(s.valor) }}</span>
          </div>
          <div v-if="a.insumos?.length" style="display: flex; gap: 6px; flex-wrap: wrap">
            <strong style="font-size: 0.78rem; color: #4a5568; align-self: center">Insumos:</strong>
            <span v-for="i in a.insumos" :key="i.id" class="badge b-blue">{{ i.nome }} ×{{ i.qtd }} · {{ fmt(i.valor * i.qtd) }}</span>
          </div>
        </div>
        <div style="margin-top: 12px"><button class="btn btn-danger" @click="excluir(a.id)">Excluir este registro</button></div>
      </div>
    </details>
  </div>
</template>
