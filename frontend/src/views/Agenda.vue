<script setup>
import { computed, onMounted, reactive, ref } from "vue";

import { agendamentosApi } from "@/api/agendamentos";
import { pacientesApi } from "@/api/pacientes";
import { servicosApi } from "@/api/servicos";
import { confirmar } from "@/stores/confirm";
import { toast } from "@/stores/toast";
import { hojeISO, STATUS_LABEL } from "@/utils";

const MESES = ["Janeiro", "Fevereiro", "Março", "Abril", "Maio", "Junho", "Julho", "Agosto", "Setembro", "Outubro", "Novembro", "Dezembro"];
const DIAS_SEMANA = ["Dom", "Seg", "Ter", "Qua", "Qui", "Sex", "Sáb"];
const STATUS_BADGE = { agendado: "b-agendado", confirmado: "b-confirmado", realizado: "b-realizado", cancelado: "b-cancelado" };

const agendamentos = ref([]);
const pacientes = ref([]);
const servicos = ref([]);

const calDate = ref(new Date());
const calSelected = ref(hojeISO());
const reagendarAberto = ref(null);
const reagData = reactive({ data: "", hora: "" });

const vazio = () => ({
  id: "",
  tipo: "livre",
  pacienteId: "",
  pacNome: "",
  tutorNome: "",
  tutorTel: "",
  data: calSelected.value,
  hora: "",
  queixa: "",
  servicosLivre: "",
  status: "agendado",
  obs: "",
});
const form = reactive(vazio());
const servicosSel = reactive(new Set());

async function carregar() {
  const [a, p, s] = await Promise.all([agendamentosApi.listar(), pacientesApi.listar(), servicosApi.listar()]);
  agendamentos.value = a;
  pacientes.value = p;
  servicos.value = s;
}

const mesLabel = computed(() => `${MESES[calDate.value.getMonth()]} ${calDate.value.getFullYear()}`);

const diasDoMes = computed(() => {
  const ano = calDate.value.getFullYear();
  const mes = calDate.value.getMonth();
  const primeiroDia = new Date(ano, mes, 1).getDay();
  const totalDias = new Date(ano, mes + 1, 0).getDate();
  const hoje = hojeISO();
  const dias = [];
  for (let i = 0; i < primeiroDia; i++) dias.push(null);
  for (let d = 1; d <= totalDias; d++) {
    const iso = `${ano}-${String(mes + 1).padStart(2, "0")}-${String(d).padStart(2, "0")}`;
    dias.push({
      dia: d,
      iso,
      hoje: iso === hoje,
      selecionado: iso === calSelected.value,
      temEvento: agendamentos.value.some((a) => a.data === iso && a.status !== "cancelado"),
    });
  }
  return dias;
});

function calPrev() {
  calDate.value = new Date(calDate.value.getFullYear(), calDate.value.getMonth() - 1, 1);
}
function calNext() {
  calDate.value = new Date(calDate.value.getFullYear(), calDate.value.getMonth() + 1, 1);
}
function calSelectDay(iso) {
  calSelected.value = iso;
  calDate.value = new Date(iso + "T12:00:00");
}

const agendamentosDoDia = computed(() =>
  agendamentos.value
    .filter((a) => a.data === calSelected.value)
    .sort((a, b) => (a.hora || "").localeCompare(b.hora || ""))
);

const proximos = computed(() =>
  agendamentos.value
    .filter((a) => a.data >= hojeISO() && a.status !== "cancelado")
    .sort((a, b) => a.data.localeCompare(b.data) || (a.hora || "").localeCompare(b.hora || ""))
    .slice(0, 8)
);

function limpar() {
  Object.assign(form, vazio());
  form.data = calSelected.value;
  servicosSel.clear();
}

function toggleServico(id) {
  servicosSel.has(id) ? servicosSel.delete(id) : servicosSel.add(id);
}

function selecionarPaciente() {
  const p = pacientes.value.find((x) => x.id === form.pacienteId);
  if (!p) return;
  form.pacNome = p.nome;
  if (p.tutor) {
    form.tutorNome = p.tutor.nome;
    form.tutorTel = p.tutor.tel || "";
  }
}

async function salvar() {
  if (!form.data) {
    toast("Informe a data.", false);
    return;
  }
  if (!form.pacNome) {
    toast("Informe o nome do paciente.", false);
    return;
  }
  const payload = {
    data: form.data,
    hora: form.hora || null,
    paciente_id: form.tipo === "cadastrado" ? form.pacienteId || null : null,
    pac_nome: form.pacNome,
    tutor_nome: form.tutorNome || null,
    tutor_tel: form.tutorTel || null,
    queixa: form.queixa || null,
    servico_ids: [...servicosSel],
    servicos_livre: form.servicosLivre || null,
    status: form.status || "agendado",
    obs: form.obs || null,
  };
  try {
    if (form.id) await agendamentosApi.atualizar(form.id, payload);
    else await agendamentosApi.criar(payload);
    toast(form.id ? "Agendamento atualizado!" : "Agendamento salvo!");
    calSelected.value = form.data;
    limpar();
    carregar();
  } catch (e) {
    toast(e.message, false);
  }
}

function editar(a) {
  Object.assign(form, {
    id: a.id,
    tipo: a.paciente_id ? "cadastrado" : "livre",
    pacienteId: a.paciente_id || "",
    pacNome: a.pac_nome || "",
    tutorNome: a.tutor_nome || "",
    tutorTel: a.tutor_tel || "",
    data: a.data,
    hora: a.hora || "",
    queixa: a.queixa || "",
    servicosLivre: a.servicos_livre || "",
    status: a.status || "agendado",
    obs: a.obs || "",
  });
  servicosSel.clear();
  (a.servicos || []).forEach((s) => servicosSel.add(s.id));
}

async function excluir(id) {
  if (!(await confirmar("Excluir este agendamento?"))) return;
  await agendamentosApi.excluir(id);
  toast("Agendamento removido.");
  carregar();
}

async function marcarRealizado(id) {
  await agendamentosApi.alterarStatus(id, "realizado");
  toast("Marcado como realizado! ✔");
  carregar();
}
async function marcarCancelado(id) {
  if (!(await confirmar("Marcar como cancelado?"))) return;
  await agendamentosApi.alterarStatus(id, "cancelado");
  toast("Atendimento cancelado.");
  carregar();
}
function abrirReagendar(a) {
  reagendarAberto.value = a.id;
  reagData.data = a.data;
  reagData.hora = a.hora || "";
}
async function confirmarReagendar(id) {
  if (!reagData.data) {
    toast("Informe a nova data.", false);
    return;
  }
  await agendamentosApi.reagendar(id, reagData.data, reagData.hora);
  toast("Reagendado!");
  reagendarAberto.value = null;
  calSelected.value = reagData.data;
  carregar();
}

onMounted(carregar);
</script>

<template>
  <div class="tab">
    <h2>📅 Agenda</h2>

    <div class="agenda-grid" style="display: grid; grid-template-columns: 1fr 1fr; gap: 20px; align-items: start">
      <div>
        <div class="cal-wrap">
          <div class="cal-nav">
            <button @click="calPrev">‹</button>
            <span>{{ mesLabel }}</span>
            <button @click="calNext">›</button>
          </div>
          <div class="cal-grid">
            <div v-for="d in DIAS_SEMANA" :key="d" class="cal-label">{{ d }}</div>
            <div v-for="(dia, idx) in diasDoMes" :key="idx" class="cal-day" :class="{ today: dia?.hoje, selected: dia?.selecionado, 'other-month': !dia }" @click="dia && calSelectDay(dia.iso)">
              <span v-if="dia">{{ dia.dia }}</span>
              <span v-if="dia?.temEvento" class="ev-dot"></span>
            </div>
          </div>
        </div>

        <div class="card">
          <div class="section-title">Agendamentos de {{ calSelected.split("-").reverse().join("/") }}</div>
          <div v-if="!agendamentosDoDia.length" class="empty"><span class="empty-icon">📅</span>Nenhum agendamento neste dia.</div>
          <div v-for="a in agendamentosDoDia" :key="a.id" class="ag-card" :class="a.status">
            <div class="ag-card-header">
              <div class="ag-hora">{{ a.hora || "—" }}</div>
              <div class="ag-card-info">
                <div class="ag-pac-name">{{ a.pac_nome }}</div>
                <div class="ag-tutor-name">👤 {{ a.tutor_nome || "—" }}{{ a.tutor_tel ? " · " + a.tutor_tel : "" }}</div>
                <div v-if="a.queixa" class="ag-queixa">🩺 {{ a.queixa }}</div>
                <div v-if="a.servicos?.length || a.servicos_livre" class="ag-servicos">
                  🔧 {{ [...(a.servicos || []).map((s) => s.nome), a.servicos_livre].filter(Boolean).join(" · ") }}
                </div>
              </div>
              <span class="badge" :class="STATUS_BADGE[a.status] || 'b-gray'">{{ STATUS_LABEL[a.status] || a.status }}</span>
            </div>
            <div v-if="a.obs" class="ag-obs">📝 {{ a.obs }}</div>
            <div class="tl-qa">
              <button v-if="a.status !== 'realizado' && a.status !== 'cancelado'" class="qa-btn qa-ok" @click="marcarRealizado(a.id)">✔ Realizado</button>
              <button v-if="a.status !== 'cancelado'" class="qa-btn qa-cancel" @click="marcarCancelado(a.id)">✕ Cancelar</button>
              <button class="qa-btn qa-reag" @click="abrirReagendar(a)">📅 Reagendar</button>
              <button class="qa-btn qa-edit" @click="editar(a)">✎ Editar</button>
              <button class="qa-btn qa-cancel" @click="excluir(a.id)">🗑 Excluir</button>
            </div>
            <div v-if="reagendarAberto === a.id" class="reag-inline open">
              <div class="reag-row">
                <div><label>Nova data</label><input v-model="reagData.data" type="date" /></div>
                <div><label>Novo horário</label><input v-model="reagData.hora" type="time" /></div>
              </div>
              <div style="display: flex; gap: 8px">
                <button class="btn btn-primary" style="font-size: 0.8rem; padding: 6px 14px" @click="confirmarReagendar(a.id)">Confirmar</button>
                <button class="btn btn-secondary" style="font-size: 0.8rem; padding: 6px 14px" @click="reagendarAberto = null">Cancelar</button>
              </div>
            </div>
          </div>
        </div>
      </div>

      <div>
        <div class="card" id="ag-form-card">
          <div class="section-title">{{ form.id ? "Editar Agendamento" : "Novo Agendamento" }}</div>
          <div class="pac-tipo-toggle">
            <label><input v-model="form.tipo" type="radio" value="livre" /> Paciente avulso</label>
            <label><input v-model="form.tipo" type="radio" value="cadastrado" /> Paciente cadastrado</label>
          </div>

          <div v-if="form.tipo === 'cadastrado'" style="margin-bottom: 10px">
            <label>Paciente</label>
            <select v-model="form.pacienteId" @change="selecionarPaciente">
              <option value="">Selecione o paciente...</option>
              <option v-for="p in pacientes" :key="p.id" :value="p.id">{{ p.nome }}{{ p.tutor ? " (" + p.tutor.nome + ")" : "" }}</option>
            </select>
          </div>

          <div class="form-grid">
            <div class="full"><label>Nome do paciente *</label><input v-model="form.pacNome" placeholder="Ex: Thor" /></div>
            <div><label>Tutor</label><input v-model="form.tutorNome" placeholder="Nome do tutor" /></div>
            <div><label>Telefone</label><input v-model="form.tutorTel" placeholder="(51) 99999-0000" /></div>
            <div><label>Data *</label><input v-model="form.data" type="date" /></div>
            <div><label>Hora</label><input v-model="form.hora" type="time" /></div>
            <div class="full"><label>Queixa</label><input v-model="form.queixa" placeholder="Motivo da consulta" /></div>
            <div class="full">
              <label>Serviços previstos</label>
              <div class="select-list">
                <div v-for="s in servicos" :key="s.id" class="item">
                  <input type="checkbox" :checked="servicosSel.has(s.id)" @change="toggleServico(s.id)" />
                  <span class="item-label">{{ s.nome }}</span>
                </div>
              </div>
            </div>
            <div class="full"><label>Outros serviços (texto livre)</label><input v-model="form.servicosLivre" placeholder="Ex: banho e tosa" /></div>
            <div>
              <label>Status</label>
              <select v-model="form.status">
                <option value="agendado">Agendado</option>
                <option value="confirmado">Confirmado</option>
                <option value="realizado">Realizado</option>
                <option value="cancelado">Cancelado</option>
              </select>
            </div>
            <div class="full"><label>Observações</label><textarea v-model="form.obs"></textarea></div>
          </div>

          <div class="form-actions">
            <button class="btn btn-primary" @click="salvar">Salvar Agendamento</button>
            <button class="btn btn-secondary" @click="limpar">Cancelar</button>
          </div>
        </div>

        <div class="card">
          <div class="section-title">Próximos Agendamentos</div>
          <div v-if="!proximos.length" style="color: #8c8a78; text-align: center; padding: 20px; font-size: 0.87rem">Nenhum próximo agendamento.</div>
          <div v-for="a in proximos" :key="a.id" class="ag-card" :class="a.status" style="cursor: pointer" @click="calSelectDay(a.data)">
            <div class="ag-card-header">
              <div class="ag-hora" style="text-align: center; font-size: 0.8rem; min-width: 36px">
                {{ a.data.split("-").reverse().join("/") }}<br /><span style="font-size: 0.9rem">{{ a.hora || "—" }}</span>
              </div>
              <div class="ag-card-info">
                <div class="ag-pac-name">{{ a.pac_nome }}</div>
                <div class="ag-tutor-name">👤 {{ a.tutor_nome || "—" }}</div>
              </div>
              <span class="badge" :class="STATUS_BADGE[a.status] || 'b-gray'" style="flex-shrink: 0">{{ STATUS_LABEL[a.status] || a.status }}</span>
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>
