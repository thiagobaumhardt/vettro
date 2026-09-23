<script setup>
import { onMounted, reactive, ref } from "vue";

import { usuariosApi } from "@/api/usuarios";
import { confirmar } from "@/stores/confirm";
import { toast } from "@/stores/toast";

const vazio = { id: "", nome: "", email: "", papel: "vet", senha: "", ativo: true };
const form = reactive({ ...vazio });
const lista = ref([]);

async function carregar() {
  lista.value = await usuariosApi.listar();
}

function cancelar() {
  Object.assign(form, vazio);
}

async function salvar() {
  if (!form.nome || !form.email || (!form.id && !form.senha)) {
    toast("Preencha nome, e-mail e senha.", false);
    return;
  }
  try {
    if (form.id) {
      const dados = { nome: form.nome, papel: form.papel, ativo: form.ativo };
      if (form.senha) dados.senha = form.senha;
      await usuariosApi.atualizar(form.id, dados);
    } else {
      await usuariosApi.criar({ nome: form.nome, email: form.email, papel: form.papel, senha: form.senha });
    }
    toast(form.id ? "Usuário atualizado!" : "Usuário cadastrado!");
    cancelar();
    carregar();
  } catch (e) {
    toast(e.message, false);
  }
}

function editar(u) {
  Object.assign(form, { id: u.id, nome: u.nome, email: u.email, papel: u.papel, senha: "", ativo: u.ativo });
}

async function excluir(u) {
  if (!(await confirmar(`Excluir o acesso de ${u.nome}?`))) return;
  await usuariosApi.excluir(u.id);
  toast("Usuário removido.");
  carregar();
}

onMounted(carregar);
</script>

<template>
  <div class="tab">
    <h2>🔑 Usuários</h2>
    <div class="card">
      <div class="section-title">{{ form.id ? "Editar Usuário" : "Novo Usuário" }}</div>
      <div class="form-grid">
        <div><label>Nome *</label><input v-model="form.nome" placeholder="Ex: Dra. Ana Souza" /></div>
        <div><label>E-mail *</label><input v-model="form.email" type="email" :readonly="!!form.id" placeholder="ana@clinica.com" /></div>
        <div>
          <label>Papel *</label>
          <select v-model="form.papel">
            <option value="vet">Veterinária (sem acesso ao faturamento)</option>
            <option value="admin">Admin (acesso total)</option>
          </select>
        </div>
        <div><label>{{ form.id ? "Nova senha (opcional)" : "Senha *" }}</label><input v-model="form.senha" type="password" placeholder="••••••••" /></div>
        <div v-if="form.id">
          <label>Status</label>
          <select v-model="form.ativo">
            <option :value="true">Ativo</option>
            <option :value="false">Inativo</option>
          </select>
        </div>
      </div>
      <div class="form-actions">
        <button class="btn btn-primary" @click="salvar">Salvar</button>
        <button class="btn btn-secondary" @click="cancelar">Cancelar</button>
      </div>
    </div>

    <div class="card">
      <div class="section-title">Usuários Cadastrados</div>
      <div class="table-wrap">
        <div v-if="!lista.length" class="empty"><span class="empty-icon">🔑</span>Nenhum usuário cadastrado.</div>
        <table v-else>
          <thead><tr><th>Nome</th><th>E-mail</th><th>Papel</th><th>Status</th><th>Ações</th></tr></thead>
          <tbody>
            <tr v-for="u in lista" :key="u.id">
              <td>{{ u.nome }}</td>
              <td>{{ u.email }}</td>
              <td><span class="badge" :class="u.papel === 'admin' ? 'b-blue' : 'b-green'">{{ u.papel === "admin" ? "Admin" : "Veterinária" }}</span></td>
              <td><span class="badge" :class="u.ativo ? 'b-pago' : 'b-pendente'">{{ u.ativo ? "Ativo" : "Inativo" }}</span></td>
              <td>
                <div class="td-actions">
                  <button class="btn btn-edit" @click="editar(u)">Editar</button>
                  <button class="btn btn-danger" @click="excluir(u)">Excluir</button>
                </div>
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>
  </div>
</template>
