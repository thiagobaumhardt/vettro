<script setup>
import { computed, onMounted, reactive, ref } from "vue";
import { useRouter } from "vue-router";

import { tutoresApi } from "@/api/tutores";
import { toast } from "@/stores/toast";
import { fmtCpf } from "@/utils";

const props = defineProps({ id: String });
const router = useRouter();

const form = reactive({
  nome: "",
  tel: "",
  email: "",
  cpf: "",
  cep: "",
  endereco: "",
  numero: "",
  complemento: "",
  bairro: "",
  cidade: "",
  uf: "",
  como_conheceu: "",
  obs: "",
  consentimento_dados: false,
});
const editando = computed(() => !!props.id);
const buscandoCep = ref(false);

const COMO_CONHECEU_OPCOES = ["WhatsApp", "Indicação", "Facebook", "Instagram", "Rádio", "TV", "Google"];

onMounted(async () => {
  if (props.id) {
    const t = await tutoresApi.obter(props.id);
    Object.assign(form, { ...t, cpf: fmtCpf(t.cpf) });
  }
});

function formatarCep() {
  const digitos = form.cep.replace(/\D/g, "").slice(0, 8);
  form.cep = digitos.length > 5 ? `${digitos.slice(0, 5)}-${digitos.slice(5)}` : digitos;
}

function formatarCpf() {
  const d = form.cpf.replace(/\D/g, "").slice(0, 11);
  form.cpf = d
    .replace(/(\d{3})(\d)/, "$1.$2")
    .replace(/(\d{3})(\d)/, "$1.$2")
    .replace(/(\d{3})(\d{1,2})$/, "$1-$2");
}

async function buscarCep() {
  const cepLimpo = form.cep.replace(/\D/g, "");
  if (cepLimpo.length !== 8) return;
  buscandoCep.value = true;
  try {
    const resp = await fetch(`https://viacep.com.br/ws/${cepLimpo}/json/`);
    const dados = await resp.json();
    if (dados.erro) {
      toast("CEP não encontrado.", false);
      return;
    }
    form.endereco = dados.logradouro || form.endereco;
    form.bairro = dados.bairro || form.bairro;
    form.cidade = dados.localidade || form.cidade;
    form.uf = dados.uf || form.uf;
  } catch (e) {
    toast("Não foi possível buscar o CEP.", false);
  } finally {
    buscandoCep.value = false;
  }
}

async function salvar() {
  if (!form.nome || !form.tel) {
    toast("Preencha nome e telefone.", false);
    return;
  }
  const dados = {
    nome: form.nome,
    tel: form.tel,
    email: form.email || null,
    cpf: form.cpf ? form.cpf.replace(/\D/g, "") : null,
    cep: form.cep || null,
    endereco: form.endereco || null,
    numero: form.numero || null,
    complemento: form.complemento || null,
    bairro: form.bairro || null,
    cidade: form.cidade || null,
    uf: form.uf || null,
    como_conheceu: form.como_conheceu || null,
    obs: form.obs || null,
    consentimento_dados: form.consentimento_dados,
  };
  try {
    if (editando.value) await tutoresApi.atualizar(props.id, dados);
    else await tutoresApi.criar(dados);
    toast(editando.value ? "Tutor atualizado!" : "Tutor cadastrado!");
    router.push("/tutores");
  } catch (e) {
    toast(e.message, false);
  }
}
</script>

<template>
  <div class="tab" style="padding-top: 20px">
    <div class="pac-subpage-header">
      <router-link class="btn btn-back" to="/tutores">← Voltar para lista</router-link>
      <h2>{{ editando ? "Editar Tutor" : "Novo Tutor" }}</h2>
    </div>
    <div class="card">
      <div class="form-grid">
        <div><label>Nome completo *</label><input v-model="form.nome" placeholder="Ex: João Silva" /></div>
        <div><label>Telefone / WhatsApp *</label><input v-model="form.tel" placeholder="(51) 99999-0000" /></div>
        <div><label>E-mail</label><input v-model="form.email" type="email" placeholder="joao@email.com" /></div>
        <div><label>CPF</label><input v-model="form.cpf" @input="formatarCpf" placeholder="000.000.000-00" maxlength="14" /></div>
        <div>
          <label>CEP</label>
          <input v-model="form.cep" @input="formatarCep" @blur="buscarCep" placeholder="00000-000" maxlength="9" />
          <p v-if="buscandoCep" style="font-size: 0.75rem; color: #8c8a78; margin-top: 4px">Buscando endereço...</p>
        </div>
        <div><label>Endereço</label><input v-model="form.endereco" placeholder="Rua, avenida..." /></div>
        <div><label>Número</label><input v-model="form.numero" placeholder="Ex: 123" /></div>
        <div><label>Complemento</label><input v-model="form.complemento" placeholder="Apto, bloco, casa..." /></div>
        <div><label>Bairro</label><input v-model="form.bairro" placeholder="Bairro" /></div>
        <div><label>Cidade</label><input v-model="form.cidade" placeholder="Cidade" /></div>
        <div><label>UF</label><input v-model="form.uf" placeholder="Ex: RS" maxlength="2" style="text-transform: uppercase" /></div>
        <div>
          <label>Como conheceu a clínica?</label>
          <select v-model="form.como_conheceu">
            <option value="">Selecione...</option>
            <option v-for="o in COMO_CONHECEU_OPCOES" :key="o" :value="o">{{ o }}</option>
          </select>
        </div>
        <div class="full"><label>Observações</label><textarea v-model="form.obs" placeholder="Informações adicionais..."></textarea></div>
        <div class="full lgpd-consent">
          <label class="lgpd-consent-label">
            <input type="checkbox" v-model="form.consentimento_dados" />
            <span>
              O tutor autoriza o uso dos dados pessoais fornecidos para fins de atendimento veterinário, conforme a
              Lei Geral de Proteção de Dados (LGPD).
            </span>
          </label>
        </div>
      </div>
      <div class="form-actions">
        <button class="btn btn-primary" @click="salvar">💾 Salvar Tutor</button>
        <router-link class="btn btn-secondary" to="/tutores">Cancelar</router-link>
      </div>
    </div>
  </div>
</template>
