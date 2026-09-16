<script setup>
import { onMounted, ref } from "vue";

import { dashboardApi } from "@/api/dashboard";
import { session } from "@/stores/session";
import { especieEmoji, fmt } from "@/utils";

const stats = ref(null);
const alerta = ref(null);
const ultimas = ref([]);
const carregando = ref(true);

const TIPO_ICON = { modulo: "📋", "ficha-atend": "🩺", cirurgia: "🔪" };

const primeiroNome = (session.usuario?.nome || "").trim().split(/\s+/)[0] || "";
const dataHoje = new Intl.DateTimeFormat("pt-BR", {
  weekday: "long",
  day: "2-digit",
  month: "long",
  year: "numeric",
}).format(new Date());

onMounted(async () => {
  try {
    const [s, a, u] = await Promise.all([
      dashboardApi.stats(),
      dashboardApi.estoqueAlerta(),
      dashboardApi.ultimas24h(),
    ]);
    stats.value = s;
    alerta.value = a;
    ultimas.value = u;
  } finally {
    carregando.value = false;
  }
});
</script>

<template>
  <div class="home-body">
    <div class="home-hero">
      <div>
        <div class="home-hero-kicker">Bem-vindo{{ primeiroNome ? "," : "" }}</div>
        <h1>{{ primeiroNome || "Vettro" }}!</h1>
        <p>Que hoje seja mais um dia de cuidado, dedicação e muitas histórias boas com nossos pacientes.</p>
      </div>
      <div class="home-hero-date"><span class="ic">📅</span>{{ dataHoje }}</div>
    </div>
    <div v-if="alerta && (alerta.zerados.length || alerta.baixos.length)" class="stock-alert-box">
      <div class="al-icon">⚠️</div>
      <div class="al-body">
        <div class="al-title">Atenção — Estoque baixo</div>
        <div class="al-items">
          <span v-for="i in alerta.zerados" :key="i.id" class="al-item">⛔ {{ i.nome }}</span>
          <span v-for="i in alerta.baixos" :key="i.id" class="al-item">⚠️ {{ i.nome }} ({{ i.qtd }})</span>
        </div>
      </div>
    </div>

    <div class="card" style="margin-bottom: 20px">
      <div class="section-title-row" style="margin-bottom: 12px">
        <span class="st-label">🕐 Atendimentos nas últimas 24h</span>
        <router-link class="btn btn-secondary" style="font-size: 0.75rem; padding: 4px 12px" to="/atendimentos"
          >Ver todos →</router-link
        >
      </div>
      <div v-if="carregando" class="empty">Carregando...</div>
      <div v-else-if="!ultimas.length" class="empty">
        <span class="empty-icon">🕐</span>Nenhum atendimento nas últimas 24h.
      </div>
      <div v-else>
        <div v-for="(item, idx) in ultimas" :key="idx" class="atend-24h-card">
          <div class="atend-24h-hora">
            {{ item.hora || "—" }}
            <small>{{ item.data }}</small>
          </div>
          <div class="atend-24h-info">
            <div class="pac">
              {{ TIPO_ICON[item.tipo] }} {{ especieEmoji(item.pac_especie) }} {{ item.pac_nome }}
            </div>
            <div class="meta">Tutor: {{ item.tutor_nome || "—" }}</div>
          </div>
          <div class="atend-24h-total">{{ fmt(item.total) }}</div>
        </div>
      </div>
    </div>

    <p style="font-size: 0.78rem; font-weight: 700; color: #8c8a78; text-transform: uppercase; letter-spacing: 0.06em; margin-bottom: 12px">
      Resumo do sistema
    </p>
    <div v-if="stats" class="stats-row">
      <router-link class="stat-card" to="/tutores">
        <div class="stat-icon">👤</div>
        <div class="stat-num">{{ stats.tutores }}</div>
        <div class="stat-label">Tutores</div>
      </router-link>
      <router-link class="stat-card" to="/pacientes">
        <div class="stat-icon">🐶</div>
        <div class="stat-num">{{ stats.pacientes }}</div>
        <div class="stat-label">Pacientes</div>
      </router-link>
      <router-link class="stat-card" to="/servicos">
        <div class="stat-icon">💉</div>
        <div class="stat-num">{{ stats.servicos }}</div>
        <div class="stat-label">Serviços</div>
      </router-link>
      <router-link class="stat-card" to="/insumos">
        <div class="stat-icon">📦</div>
        <div class="stat-num">{{ stats.insumos }}</div>
        <div class="stat-label">Insumos</div>
      </router-link>
      <router-link class="stat-card" to="/atendimentos">
        <div class="stat-icon">📋</div>
        <div class="stat-num">{{ stats.atendimentos }}</div>
        <div class="stat-label">Atendimentos</div>
      </router-link>
      <router-link class="stat-card" to="/agenda">
        <div class="stat-icon">📅</div>
        <div class="stat-num">{{ stats.agendados }}</div>
        <div class="stat-label">Agendados</div>
      </router-link>
    </div>

    <p style="font-size: 0.78rem; font-weight: 700; color: #8c8a78; text-transform: uppercase; letter-spacing: 0.06em; margin-bottom: 12px">
      Acesso rápido
    </p>
    <div class="nav-cards">
      <router-link class="nav-card" to="/tutores">
        <div class="nc-icon">👤</div>
        <h3>Tutores</h3>
        <p>Cadastre os responsáveis pelos animais. Cada tutor pode ter múltiplos pets vinculados.</p>
        <div class="nc-arrow">→</div>
      </router-link>
      <router-link class="nav-card" to="/pacientes">
        <div class="nc-icon">🐶</div>
        <h3>Pacientes</h3>
        <p>Gerencie os animais atendidos. Acesse a ficha completa com anamnese, exames e fotos.</p>
        <div class="nc-arrow">→</div>
      </router-link>
      <router-link class="nav-card" to="/servicos">
        <div class="nc-icon">💉</div>
        <h3>Serviços</h3>
        <p>Cadastre os serviços oferecidos e seus valores para usar nas cobranças.</p>
        <div class="nc-arrow">→</div>
      </router-link>
      <router-link class="nav-card" to="/insumos">
        <div class="nc-icon">📦</div>
        <h3>Insumos</h3>
        <p>Controle o estoque de materiais e medicamentos utilizados nos atendimentos.</p>
        <div class="nc-arrow">→</div>
      </router-link>
      <router-link class="nav-card" to="/agenda">
        <div class="nc-icon">📅</div>
        <h3>Agenda</h3>
        <p>Agende consultas no calendário. Selecione pacientes cadastrados ou digite livremente.</p>
        <div class="nc-arrow">→</div>
      </router-link>
      <router-link class="nav-card" to="/atendimentos">
        <div class="nc-icon">📋</div>
        <h3>Atendimentos</h3>
        <p>Registre atendimentos vinculando paciente, serviços realizados e insumos utilizados.</p>
        <div class="nc-arrow">→</div>
      </router-link>
    </div>
  </div>
</template>
