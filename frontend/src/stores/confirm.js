import { reactive } from "vue";

export const confirmState = reactive({ show: false, mensagem: "", resolver: null });

export function confirmar(mensagem) {
  return new Promise((resolve) => {
    confirmState.mensagem = mensagem;
    confirmState.show = true;
    confirmState.resolver = resolve;
  });
}

export function responderConfirm(valor) {
  confirmState.show = false;
  confirmState.resolver?.(valor);
  confirmState.resolver = null;
}
