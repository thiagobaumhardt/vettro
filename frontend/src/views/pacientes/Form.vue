<script setup>
import { computed, onMounted, reactive, ref } from "vue";
import { useRouter } from "vue-router";

import { pacientesApi } from "@/api/pacientes";
import { tutoresApi } from "@/api/tutores";
import { toast } from "@/stores/toast";
import { especieEmoji, hojeISO } from "@/utils";

const props = defineProps({ id: String });
const router = useRouter();

const form = reactive({
  nome: "",
  especie: "",
  raca: "",
  peso: "",
  data_nascimento: "",
  tutor_id: "",
  obs: "",
  foto_perfil: null,
});
const tutores = ref([]);
const editando = computed(() => !!props.id);

const racasCao = [
  "SRD (Vira-lata)",
  "Labrador Retriever",
  "Golden Retriever",
  "Poodle",
  "Bulldog Francês",
  "Bulldog Inglês",
  "Pastor Alemão",
  "Rottweiler",
  "Yorkshire Terrier",
  "Shih Tzu",
  "Lhasa Apso",
  "Pinscher",
  "Chihuahua",
  "Beagle",
  "Dachshund (Salsicha)",
  "Border Collie",
  "Cocker Spaniel",
  "Maltês",
  "Pug",
  "Boxer",
  "Dálmata",
  "Husky Siberiano",
  "Akita",
  "Basset Hound",
  "Fox Paulistinha",
  "Spitz Alemão (Lulu da Pomerânia)",
  "Schnauzer",
  "Pit Bull",
  "Doberman",
  "Weimaraner",
  "Setter Irlandês",
  "São Bernardo",
  "Cane Corso",
  "Dogue Alemão",
  "Fila Brasileiro",
  "Bull Terrier",
  "American Staffordshire Terrier",
  "Shar Pei",
  "Chow Chow",
  "Buldogue Campeiro",
  "Whippet",
  "Pastor Belga (Malinois)",
  "Rhodesian Ridgeback",
  "Boiadeiro Bernês",
  "Australian Shepherd",
  "Jack Russell Terrier",
  "West Highland White Terrier",
  "Bichon Frisé",
  "Papillon",
  "Shiba Inu",
  "Samoieda",
  "Alaskan Malamute",
  "Galgo",
  "Cavalier King Charles Spaniel",
  "Outra",
];

const racasGato = [
  "SRD (Vira-lata)",
  "Persa",
  "Siamês",
  "Maine Coon",
  "Angorá",
  "Sphynx",
  "Ragdoll",
  "British Shorthair",
  "Bengal",
  "Munchkin",
  "Himalaio",
  "Exótico de Pelo Curto",
  "Norueguês da Floresta",
  "Azul Russo",
  "Manx",
  "Abissínio",
  "Burmês",
  "Bombaim",
  "Sagrado da Birmânia",
  "American Shorthair",
  "Devon Rex",
  "Cornish Rex",
  "Selkirk Rex",
  "Ocicat",
  "Savannah",
  "Scottish Fold",
  "Van Turco",
  "Chartreux",
  "Korat",
  "Somali",
  "Egyptian Mau",
  "Outra",
];

const racasPorEspecie = computed(() => {
  if (form.especie === "Cão") return racasCao;
  if (form.especie === "Gato") return racasGato;
  return null;
});

function onEspecieChange() {
  form.raca = "";
}

onMounted(async () => {
  tutores.value = await tutoresApi.listar();
  if (props.id) {
    const p = await pacientesApi.obter(props.id);
    Object.assign(form, {
      nome: p.nome,
      especie: p.especie,
      raca: p.raca || "",
      peso: p.peso ?? "",
      data_nascimento: p.data_nascimento || "",
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
    data_nascimento: form.data_nascimento || null,
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
          <div style="display: flex; align-items: center; gap: 8px">
            <select v-model="form.especie" @change="onEspecieChange" style="flex: 1">
              <option value="">Selecione...</option>
              <option>Cão</option>
              <option>Gato</option>
              <option>Outro</option>
            </select>
            <span v-if="form.especie" style="font-size: 1.4rem" :title="form.especie">{{ especieEmoji(form.especie) }}</span>
          </div>
        </div>
        <div>
          <label>Raça</label>
          <select v-if="racasPorEspecie" v-model="form.raca">
            <option value="">Selecione...</option>
            <option v-for="r in racasPorEspecie" :key="r" :value="r">{{ r }}</option>
          </select>
          <input
            v-else
            v-model="form.raca"
            :disabled="!form.especie"
            :placeholder="form.especie ? 'Ex: Golden Retriever' : 'Selecione a espécie primeiro'"
          />
        </div>
        <div><label>Peso (kg)</label><input v-model="form.peso" type="number" step="0.1" min="0" placeholder="Ex: 8.5" /></div>
        <div><label>Data de Nascimento</label><input v-model="form.data_nascimento" type="date" :max="hojeISO()" /></div>
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
