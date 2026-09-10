<script setup>
import { computed, onMounted, ref, watch } from "vue";
import { useRoute } from "vue-router";

import { pacientesApi } from "@/api/pacientes";
import { session } from "@/stores/session";
import { especieEmoji } from "@/utils";

import FichaAnamnese from "./ficha/FichaAnamnese.vue";
import FichaCirurgias from "./ficha/FichaCirurgias.vue";
import FichaCobrancas from "./ficha/FichaCobrancas.vue";
import FichaExames from "./ficha/FichaExames.vue";
import FichaFotos from "./ficha/FichaFotos.vue";
import FichaInfo from "./ficha/FichaInfo.vue";
import FichaNotas from "./ficha/FichaNotas.vue";

const props = defineProps({ id: String });
const route = useRoute();

const paciente = ref(null);
const aba = ref("ficha");

const ABAS = [
  { key: "ficha", label: "📋 Ficha" },
  { key: "anamnese", label: "🩺 Anamnese" },
  { key: "cirurgias", label: "🔪 Cirurgias" },
  { key: "exames", label: "📄 Exames" },
  { key: "fotos", label: "🖼️ Fotos" },
  { key: "cobranca", label: "💰 Cobrança", admin: true },
  { key: "notas", label: "📝 Anotações" },
];

const abasVisiveis = computed(() => ABAS.filter((a) => !a.admin || session.admin));

async function carregar() {
  paciente.value = await pacientesApi.obter(props.id);
}

watch(
  () => route.query.aba,
  (v) => {
    if (v) aba.value = v;
  },
  { immediate: true }
);

onMounted(carregar);
</script>

<template>
  <div v-if="paciente">
    <div class="inner-header">
      <div class="avatar-circle avatar-sm">
        <img v-if="paciente.foto_perfil" :src="paciente.foto_perfil" />
        <span v-else>{{ especieEmoji(paciente.especie) }}</span>
      </div>
      <div class="inner-header-info" style="flex: 1">
        <h2>{{ paciente.nome }}</h2>
        <p>{{ paciente.especie }}{{ paciente.raca ? " · " + paciente.raca : "" }}</p>
      </div>
      <router-link class="btn btn-back" to="/pacientes">← Voltar</router-link>
      <router-link class="btn btn-edit" :to="`/pacientes/${paciente.id}/editar`">Editar Ficha</router-link>
    </div>

    <div class="pac-tabs">
      <button v-for="a in abasVisiveis" :key="a.key" :class="{ active: aba === a.key }" @click="aba = a.key">
        {{ a.label }}
      </button>
    </div>

    <div class="pac-tab-content active">
      <FichaInfo v-if="aba === 'ficha'" :paciente="paciente" />
      <FichaAnamnese v-else-if="aba === 'anamnese'" :paciente="paciente" />
      <FichaCirurgias v-else-if="aba === 'cirurgias'" :paciente="paciente" />
      <FichaExames v-else-if="aba === 'exames'" :paciente-id="paciente.id" />
      <FichaFotos v-else-if="aba === 'fotos'" :paciente-id="paciente.id" />
      <FichaCobrancas v-else-if="aba === 'cobranca' && session.admin" :paciente-id="paciente.id" />
      <FichaNotas v-else-if="aba === 'notas'" :paciente-id="paciente.id" />
    </div>
  </div>
</template>
