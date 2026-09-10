import { reactive } from "vue";

export const toastState = reactive({ msg: "", ok: true, show: false });

let timer = null;

export function toast(msg, ok = true) {
  toastState.msg = msg;
  toastState.ok = ok;
  toastState.show = true;
  clearTimeout(timer);
  timer = setTimeout(() => {
    toastState.show = false;
  }, 2800);
}
