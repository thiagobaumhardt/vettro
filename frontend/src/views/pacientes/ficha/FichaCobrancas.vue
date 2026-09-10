<script setup>
import { computed, onMounted, reactive, ref } from "vue";

import { cobrancasApi } from "@/api/ficha";
import { insumosApi } from "@/api/insumos";
import { servicosApi } from "@/api/servicos";
import { toast } from "@/stores/toast";
import { fmt } from "@/utils";

const props = defineProps({ pacienteId: String });

const servicos = ref([]);
const insumos = ref([]);
const hist = ref([]);
const obs = ref("");
const servicosSel = reactive(new Set());
const insumosSel = reactive({});

const total = computed(() => {
  const ts = servicos.value.filter((s) => servicosSel.has(s.id)).reduce((acc, s) => acc + s.valor, 0);
  const ti = insumos.value.filter((i) => insumosSel[i.id] !== undefined).reduce((acc, i) => acc + i.valor * (insumosSel[i.id] || 1), 0);
  return ts + ti;
});

function toggleServico(id) {
  servicosSel.has(id) ? servicosSel.delete(id) : servicosSel.add(id);
}
function toggleInsumo(id) {
  if (insumosSel[id] !== undefined) delete insumosSel[id];
  else insumosSel[id] = 1;
}

async function carregar() {
  const [s, i, h] = await Promise.all([servicosApi.listar(), insumosApi.listar(), cobrancasApi.listar(props.pacienteId)]);
  servicos.value = s;
  insumos.value = i;
  hist.value = h;
}

function limpar() {
  servicosSel.clear();
  Object.keys(insumosSel).forEach((k) => delete insumosSel[k]);
  obs.value = "";
}

async function salvar() {
  if (!servicosSel.size && !Object.keys(insumosSel).length) {
    toast("Selecione ao menos um item.", false);
    return;
  }
  const payload = {
    servico_ids: [...servicosSel],
    insumos: Object.entries(insumosSel).map(([id, qtd]) => ({ id, qtd })),
    obs: obs.value || null,
  };
  try {
    await cobrancasApi.criar(props.pacienteId, payload);
    toast("Cobrança salva! Estoque atualizado.");
    limpar();
    carregar();
  } catch (e) {
    toast(e.message, false);
  }
}

async function marcarPago(id) {
  await cobrancasApi.marcarPago(id);
  toast("Marcado como pago!");
  carregar();
}

async function excluir(id) {
  if (!confirm("Excluir?")) return;
  await cobrancasApi.excluir(id);
  toast("Cobrança removida.");
  carregar();
}

onMounted(carregar);
</script>

<template>
  <div class="card">
    <div class="section-title">Nova Cobrança</div>
    <div class="form-grid">
      <div>
        <label>Serviços</label>
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
        <label>Insumos</label>
        <div class="select-list">
          <div v-if="!insumos.length" style="padding: 12px; color: #a0aec0; font-size: 0.85rem">Nenhum insumo cadastrado.</div>
          <div v-for="i in insumos" :key="i.id" class="item">
            <input type="checkbox" :checked="insumosSel[i.id] !== undefined" @change="toggleInsumo(i.id)" />
            <span class="item-label">{{ i.nome }} <small style="color: #a0aec0">(est: {{ i.qtd }})</small></span>
            <input v-if="insumosSel[i.id] !== undefined" class="qty-input" type="number" min="1" v-model.number="insumosSel[i.id]" />
          </div>
        </div>
      </div>
      <div class="full"><label>Observações</label><textarea v-model="obs" placeholder="Detalhes da cobrança..."></textarea></div>
    </div>

    <div class="total-box">
      <span class="total-label">Total</span>
      <span class="total-value">{{ fmt(total) }}</span>
    </div>

    <div class="form-actions">
      <button class="btn btn-primary" @click="salvar">💾 Salvar Cobrança</button>
      <button class="btn btn-secondary" @click="limpar">Limpar</button>
    </div>
  </div>

  <div class="card">
    <div class="section-title">Histórico de Cobranças</div>
    <div v-if="!hist.length" class="empty"><span class="empty-icon">💰</span>Nenhuma cobrança registrada.</div>
    <div v-for="c in hist" :key="c.id" class="cobr-card" :class="{ pago: c.status === 'pago' }">
      <div class="cobr-top">
        <div>
          <h4 style="font-size: 0.95rem; color: #2d3748">
            {{ new Date(c.criado_em).toLocaleString("pt-BR") }}
            <span class="badge" :class="c.status === 'pago' ? 'b-pago' : 'b-pendente'">{{ c.status === "pago" ? "✔ Pago" : "⏳ Pendente" }}</span>
          </h4>
          <div v-if="c.tutor_nome" style="font-size: 0.8rem; color: #718096; margin-top: 3px">Tutor: {{ c.tutor_nome }}</div>
        </div>
        <div class="cobr-valor">{{ fmt(c.total) }}</div>
      </div>
      <div v-if="c.servicos?.length" style="display: flex; gap: 6px; flex-wrap: wrap; margin-bottom: 6px">
        <strong style="font-size: 0.78rem; color: #4a5568; align-self: center">Serviços:</strong>
        <span v-for="s in c.servicos" :key="s.id" class="badge b-green">{{ s.nome }} · {{ fmt(s.valor) }}</span>
      </div>
      <div v-if="c.insumos?.length" style="display: flex; gap: 6px; flex-wrap: wrap; margin-bottom: 6px">
        <strong style="font-size: 0.78rem; color: #4a5568; align-self: center">Insumos:</strong>
        <span v-for="i in c.insumos" :key="i.id" class="badge b-blue">{{ i.nome }} ×{{ i.qtd }} · {{ fmt(i.valor * i.qtd) }}</span>
      </div>
      <div v-if="c.obs" style="font-size: 0.83rem; color: #718096; margin-top: 4px">📝 {{ c.obs }}</div>
      <div class="cobr-actions">
        <button v-if="c.status === 'pendente'" class="btn btn-pago" @click="marcarPago(c.id)">✔ Marcar como Pago</button>
        <span v-else style="font-size: 0.82rem; color: #276749; font-weight: 600">✔ Pagamento confirmado</span>
        <button class="btn btn-danger" @click="excluir(c.id)">Excluir</button>
      </div>
    </div>
  </div>
</template>
