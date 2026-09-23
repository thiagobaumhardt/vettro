<script setup>
import { confirmState, responderConfirm } from "@/stores/confirm";
</script>

<template>
  <div v-if="confirmState.show" class="modal-backdrop" @click="responderConfirm(false)">
    <div class="modal-card" @click.stop>
      <p class="modal-msg">{{ confirmState.mensagem }}</p>
      <div class="modal-actions">
        <button class="btn btn-secondary" @click="responderConfirm(false)">Cancelar</button>
        <button class="btn btn-danger" style="font-size: 0.88rem; padding: 9px 20px" @click="responderConfirm(true)">Confirmar</button>
      </div>
    </div>
  </div>
</template>
