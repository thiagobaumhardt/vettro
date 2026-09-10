<script setup>
import { toastState } from "@/stores/toast";
</script>

<template>
  <div id="toast" :class="['toast', toastState.show ? 'show' : '', toastState.ok ? 'ok' : 'err']">
    {{ toastState.msg }}
  </div>
</template>
