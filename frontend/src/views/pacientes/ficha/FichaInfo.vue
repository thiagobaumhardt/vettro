<script setup>
defineProps({ paciente: Object });
</script>

<template>
  <div v-if="paciente.tutor" class="tutor-banner" style="margin-bottom: 20px">
    <div class="tinfo">
      <h4>👤 {{ paciente.tutor.nome }}</h4>
      <p>{{ paciente.tutor.tel }}</p>
    </div>
    <router-link class="btn btn-secondary" :to="`/tutores/${paciente.tutor.id}`">Ver tutor</router-link>
  </div>

  <div class="card">
    <div class="section-title">Dados do Animal</div>
    <div class="info-grid">
      <div class="info-item"><label>Nome</label><p>{{ paciente.nome }}</p></div>
      <div class="info-item"><label>Espécie</label><p>{{ paciente.especie }}</p></div>
      <div class="info-item"><label>Raça</label><p>{{ paciente.raca || "—" }}</p></div>
      <div class="info-item"><label>Peso</label><p>{{ paciente.peso ? paciente.peso + " kg" : "—" }}</p></div>
      <div class="info-item"><label>Idade</label><p>{{ paciente.idade || "—" }}</p></div>
    </div>
    <div v-if="paciente.obs" style="margin-top: 16px">
      <label style="font-size: 0.72rem; font-weight: 700; text-transform: uppercase; letter-spacing: 0.05em; color: #a0aec0">Observações</label>
      <p style="font-size: 0.9rem; color: #2d3748; margin-top: 4px; white-space: pre-wrap">{{ paciente.obs }}</p>
    </div>
  </div>
</template>
