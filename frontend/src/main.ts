import { createSSRApp } from "vue";
import App from "./App.vue";
import { installDiagnostics, recordError } from './utils/diagnostics';

export function createApp() {
  const app = createSSRApp(App);
  // Vue 层兜底：组件内抛出的异常统一进诊断现场（uni.onError 收 app 级错误）。
  // 采集逻辑放在 utils/diagnostics.ts，App.vue 只管生命周期。
  app.config.errorHandler = (error, _instance, info) => {
    recordError(error, `vue:${info || 'errorHandler'}`, (error as Error)?.stack);
  };
  installDiagnostics();
  return {
    app,
  };
}
