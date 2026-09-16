<script setup>
import { onMounted, ref } from "vue";

import { tutoresApi } from "@/api/tutores";
import { especieEmoji } from "@/utils";

const props = defineProps({ id: String });

const tutor = ref(null);
const animais = ref([]);

onMounted(async () => {
  tutor.value = await tutoresApi.obter(props.id);
  animais.value = await tutoresApi.pacientes(props.id);
});
</script>

<template>
  <div class="tab" v-if="tutor">
    <div class="pac-subpage-header">
      <router-link class="btn btn-back" to="/tutores">← Voltar para tutores</router-link>
      <h2>👤 {{ tutor.nome }}</h2>
    </div>

    <div class="card">
      <div class="info-grid">
        <div class="info-item"><label>Telefone</label><p>{{ tutor.tel }}</p></div>
        <div class="info-item"><label>E-mail</label><p>{{ tutor.email || "—" }}</p></div>
        <div class="info-item"><label>CPF</label><p>{{ tutor.cpf || "—" }}</p></div>
        <div class="info-item"><label>Endereço</label><p>{{ tutor.endereco || "—" }}</p></div>
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
