<script setup>
import { computed, onMounted, reactive, ref } from "vue";
import { useRouter } from "vue-router";

import { pacientesApi } from "@/api/pacientes";
import { tutoresApi } from "@/api/tutores";
import { toast } from "@/stores/toast";

const props = defineProps({ id: String });
const router = useRouter();

const form = reactive({
  nome: "",
  especie: "",
  raca: "",
  peso: "",
  idade: "",
  tutor_id: "",
  obs: "",
  foto_perfil: null,
});
const tutores = ref([]);
const editando = computed(() => !!props.id);

onMounted(async () => {
  tutores.value = await tutoresApi.listar();
  if (props.id) {
    const p = await pacientesApi.obter(props.id);
    Object.assign(form, {
      nome: p.nome,
      especie: p.especie,
      raca: p.raca || "",
      peso: p.peso ?? "",
      idade: p.idade || "",
      tutor_id: p.tutor_id,
      obs: p.obs || "",
      foto_perfil: p.foto_perfil || null,
    });
  }
});

function previewFoto(ev) {
  const file = ev.target.files[0];
  if (!file) return;
  if (file.size > 3 * 1024 * 1024) {
    toast("A foto deve ter no máximo 3 MB.", false);
    return;
  }
  const reader = new FileReader();
  reader.onload = (e) => {
    form.foto_perfil = e.target.result;
  };
  reader.readAsDataURL(file);
}

async function salvar() {
  if (!form.nome || !form.especie || !form.tutor_id) {
    toast("Preencha nome, espécie e tutor.", false);
    return;
  }
  const dados = {
    nome: form.nome,
    especie: form.especie,
    raca: form.raca || null,
    peso: form.peso === "" ? null : Number(form.peso),
    idade: form.idade || null,
    tutor_id: form.tutor_id,
    obs: form.obs || null,
    foto_perfil: form.foto_perfil,
  };
  try {
    if (editando.value) await pacientesApi.atualizar(props.id, dados);
    else await pacientesApi.criar(dados);
    toast(editando.value ? "Paciente atualizado!" : "Paciente cadastrado!");
    router.push("/pacientes");
  } catch (e) {
    toast(e.message, false);
  }
}
</script>

<template>
  <div class="tab" style="padding-top: 20px">
    <div class="pac-subpage-header">
      <router-link class="btn btn-back" to="/pacientes">← Voltar para lista</router-link>
      <h2>{{ editando ? "Editar Paciente" : "Novo Paciente" }}</h2>
    </div>
    <div class="card">
      <div class="form-photo-row">
        <div class="avatar-circle avatar-lg">
          <img v-if="form.foto_perfil" :src="form.foto_perfil" />
          <span v-else>🐾</span>
        </div>
        <div>
          <label class="upload-label" style="margin-bottom: 6px; display: inline-flex">
            📷 Escolher foto de perfil
            <input type="file" accept="image/*" @change="previewFoto" />
          </label>
          <p style="font-size: 0.78rem; color: #8c8a78; margin-top: 4px">Formatos: JPG, PNG · Máx. 3 MB</p>
        </div>
      </div>
      <div class="form-grid">
        <div><label>Nome do Animal *</label><input v-model="form.nome" placeholder="Ex: Thor" /></div>
        <div>
          <label>Espécie *</label>
          <select v-model="form.especie">
            <option value="">Selecione...</option>
            <option>Cachorro</option>
            <option>Gato</option>
            <option>Ave</option>
            <option>Roedor</option>
            <option>Réptil</option>
            <option>Outro</option>
          </select>
        </div>
        <div><label>Raça</label><input v-model="form.raca" placeholder="Ex: Golden Retriever" /></div>
        <div><label>Peso (kg)</label><input v-model="form.peso" type="number" step="0.1" min="0" placeholder="Ex: 8.5" /></div>
        <div><label>Idade</label><input v-model="form.idade" placeholder="Ex: 3 anos" /></div>
        <div class="full">
          <label>Tutor * <span style="font-weight: 400; color: #8c8a78">— cadastre em 👤 Tutores</span></label>
          <select v-model="form.tutor_id">
            <option value="">Selecione o tutor...</option>
            <option v-for="t in tutores" :key="t.id" :value="t.id">{{ t.nome }} — {{ t.tel }}</option>
          </select>
        </div>
        <div class="full"><label>Observações</label><textarea v-model="form.obs" placeholder="Condições especiais, alergias..."></textarea></div>
      </div>
      <div class="form-actions">
        <button class="btn btn-primary" @click="salvar">💾 Salvar Paciente</button>
        <router-link class="btn btn-secondary" to="/pacientes">Cancelar</router-link>
      </div>
    </div>
  </div>
</template>
