<script setup>
import { computed, onMounted, ref } from "vue";

import { tutoresApi } from "@/api/tutores";
import { session } from "@/stores/session";
import { toast } from "@/stores/toast";
import { especieEmoji, fmtCpf, fmtData } from "@/utils";

const props = defineProps({ id: String });

const tutor = ref(null);
const animais = ref([]);

const enderecoCompleto = computed(() => {
  if (!tutor.value) return "";
  const { endereco, numero, complemento, bairro, cidade, uf, cep } = tutor.value;
  const linha1 = [endereco, numero].filter(Boolean).join(", ") + (complemento ? ` - ${complemento}` : "");
  const linha2 = [bairro, cidade && uf ? `${cidade}/${uf}` : cidade || uf].filter(Boolean).join(" - ");
  return [linha1.trim().replace(/^,\s*/, ""), linha2, cep].filter(Boolean).join(" · ");
});

onMounted(async () => {
  tutor.value = await tutoresApi.obter(props.id);
  animais.value = await tutoresApi.pacientes(props.id);
});

async function exportarDados() {
  try {
    const dados = await tutoresApi.exportarDados(props.id);
    const blob = new Blob([JSON.stringify(dados, null, 2)], { type: "application/json" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `vettro-dados-${tutor.value.nome.replace(/\s+/g, "_").toLowerCase()}.json`;
    a.click();
    URL.revokeObjectURL(url);
    toast("Dados exportados.");
  } catch (e) {
    toast(e.message, false);
  }
}
</script>

<template>
  <div class="tab" v-if="tutor">
    <div class="pac-subpage-header">
      <router-link class="btn btn-back" to="/tutores">← Voltar para tutores</router-link>
      <h2 style="flex: 1">👤 {{ tutor.nome }}</h2>
      <button v-if="session.admin" class="btn btn-secondary" @click="exportarDados">⬇ Exportar dados (LGPD)</button>
    </div>

    <div class="card">
      <div class="info-grid">
        <div class="info-item"><label>Telefone</label><p>{{ tutor.tel }}</p></div>
        <div class="info-item"><label>E-mail</label><p>{{ tutor.email || "—" }}</p></div>
        <div class="info-item"><label>CPF</label><p>{{ fmtCpf(tutor.cpf) || "—" }}</p></div>
        <div class="info-item"><label>Como conheceu</label><p>{{ tutor.como_conheceu || "—" }}</p></div>
        <div class="info-item">
          <label>Endereço</label>
          <p>{{ enderecoCompleto || "—" }}</p>
        </div>
        <div class="info-item">
          <label>Consentimento LGPD</label>
          <p>
            {{ tutor.consentimento_dados ? "✅ Autorizado" : "❌ Não autorizado" }}
            <span v-if="tutor.consentimento_em" style="color: #8c8a78">— em {{ fmtData(tutor.consentimento_em.slice(0, 10)) }}</span>
          </p>
        </div>
      </div>
      <p v-if="tutor.obs" style="margin-top: 14px; font-size: 0.88rem; color: #3f3f33">📝 {{ tutor.obs }}</p>
    </div>

    <div class="card">
      <div class="section-title">Animais deste tutor</div>
      <div v-if="!animais.length" class="empty"><span class="empty-icon">🐾</span>Nenhum animal cadastrado para este tutor.</div>
      <router-link v-for="p in animais" :key="p.id" class="animal-card" :to="`/pacientes/${p.id}`">
        <div class="animal-icon">{{ especieEmoji(p.especie) }}</div>
        <div class="animal-info">
          <h4>{{ p.nome }}</h4>
          <p>{{ p.especie }}{{ p.raca ? " · " + p.raca : "" }}</p>
        </div>
        <div class="arrow">→</div>
      </router-link>
    </div>
  </div>
</template>
