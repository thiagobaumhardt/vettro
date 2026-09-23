<script setup>
import { onMounted, ref } from "vue";

import { auditoriaApi } from "@/api/auditoria";
import { fmtDataHora } from "@/utils";

const lista = ref([]);
const entidade = ref("");

const ACAO_LABEL = {
  login_ok: "Login realizado",
  login_falha: "Login falhou",
  criar: "Criou",
  atualizar: "Atualizou",
  excluir: "Excluiu",
  exportar: "Exportou dados",
};

const ENTIDADE_LABEL = { tutor: "Tutor", paciente: "Paciente", usuario: "Usuário", auth: "Autenticação" };

async function carregar() {
  lista.value = await auditoriaApi.listar(entidade.value);
}

onMounted(carregar);
</script>

<template>
  <div class="tab">
    <h2>🛡️ Auditoria</h2>
    <p style="font-size: 0.85rem; color: #6e6c5c; margin: -8px 0 18px">
      Registro de ações sensíveis (login, criação/edição/exclusão de tutores e pacientes) — trilha de rastreabilidade
      exigida pela LGPD.
    </p>
    <div class="card">
      <div class="search-bar">
        <select v-model="entidade" @change="carregar" style="max-width: 220px">
          <option value="">Todas as entidades</option>
          <option value="auth">Autenticação</option>
          <option value="tutor">Tutor</option>
          <option value="paciente">Paciente</option>
        </select>
      </div>
      <div class="table-wrap">
        <div v-if="!lista.length" class="empty"><span class="empty-icon">🛡️</span>Nenhum evento registrado.</div>
        <table v-else>
          <thead>
            <tr><th>Quando</th><th>Usuário</th><th>Ação</th><th>Entidade</th><th>Detalhe</th><th>IP</th></tr>
          </thead>
          <tbody>
            <tr v-for="e in lista" :key="e.id">
              <td>{{ fmtDataHora(e.criado_em) }}</td>
              <td>{{ e.usuario_nome || "—" }}</td>
              <td>
                <span class="badge" :class="e.acao === 'login_falha' ? 'b-pendente' : 'b-pago'">{{ ACAO_LABEL[e.acao] || e.acao }}</span>
              </td>
              <td>{{ ENTIDADE_LABEL[e.entidade] || e.entidade }}</td>
              <td>{{ e.detalhe || "—" }}</td>
              <td>{{ e.ip || "—" }}</td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>
  </div>
</template>
