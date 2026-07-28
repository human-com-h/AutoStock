<script setup lang="ts">
import { computed, onMounted, ref } from "vue";
import { showFailToast, showSuccessToast } from "vant";
import { useRoute, useRouter } from "vue-router";
import { getMeta } from "../db/schema";
import { probeHealth } from "../services/api";
import { exchangePairingCode, initializeFromServer } from "../services/bootstrap";
import { useAppStore } from "../stores/app";

const route = useRoute();
const router = useRouter();
const appStore = useAppStore();
const code = ref("");
const deviceName = ref("我的手机");
const trusted = ref(false);
const pairing = ref(false);
const progress = ref(0);
const progressText = ref("");
const serverHost = computed(() => window.location.hostname || "电脑IP");
const caUrl = computed(() => `http://${serverHost.value}:8757/ca.crt`);
const httpsUrl = computed(() => `https://${serverHost.value}:8756/m/`);

const steps = computed(() => [
  ["下载 CA 证书", "点击下方按钮下载 ca.crt。"],
  ["打开系统设置", "安全 → 加密与凭据 → 安装证书 → CA 证书。"],
  ["确认安装", "选择刚下载的 ca.crt，并确认 AutoStock Local CA。"],
  ["返回检测", "回到 Chrome 点击“安装好了，检测一下”。"],
  ["添加到主屏幕", "Chrome 菜单 → 添加到主屏幕。"],
]);

async function detect(): Promise<void> {
  trusted.value = await probeHealth();
  if (trusted.value) showSuccessToast("HTTPS 连接正常");
  else showFailToast("暂时无法连接，请确认 CA 已安装且电脑服务正在运行");
}

async function pair(): Promise<void> {
  if (!/^\d{6}$/.test(code.value)) {
    showFailToast("请输入 6 位配对码");
    return;
  }
  pairing.value = true;
  appStore.setSyncing(true);
  try {
    await exchangePairingCode(code.value, deviceName.value);
    await initializeFromServer((current, total) => {
      progress.value = total ? Math.min(100, Math.round((current / total) * 100)) : 100;
      progressText.value = `正在初始化零件 ${Math.min(current, total)} / ${total}`;
    });
    appStore.initialized = true;
    await appStore.bootstrapState();
    showSuccessToast("配对与初始化完成");
    await router.replace("/");
  } catch (error) {
    showFailToast(error instanceof Error ? error.message : "配对失败");
  } finally {
    pairing.value = false;
    appStore.setSyncing(false);
  }
}

onMounted(async () => {
  const pairValue =
    String(route.query.pair || "") ||
    new URLSearchParams(window.location.search).get("pair") ||
    "";
  code.value = pairValue;
  const existingName = await getMeta("device_name");
  if (existingName) deviceName.value = existingName;
  trusted.value = await probeHealth();
});
</script>

<template>
  <section class="setup-page">
    <header class="setup-header">
      <button type="button" aria-label="返回" @click="router.back()"><van-icon name="arrow-left" /></button>
      <div><strong>连接 AutoStock</strong><span>安装证书、配对并初始化本地库存</span></div>
    </header>
    <div class="setup-content">
      <div class="trust-card">
        <van-icon name="shield-o" />
        <div><strong>第一步：信任这台电脑</strong><span>仅需在每台手机上操作一次</span></div>
      </div>

      <h2 class="android-title"><van-icon name="graphic" /> Android 安装步骤</h2>
      <ol class="guide-list">
        <li v-for="([title, detail], index) in steps" :key="title">
          <span>{{ index + 1 }}</span>
          <div><strong>{{ title }}</strong><p>{{ detail }}</p></div>
        </li>
      </ol>
      <a class="download-button" :href="caUrl">
        <van-icon name="down" /> 下载 AutoStock CA 证书
      </a>
      <p class="url-note">证书安装后将访问：{{ httpsUrl }}</p>
      <van-button block plain type="primary" @click="detect">
        安装好了，检测一下
      </van-button>
      <div class="detect-result" :class="{ success: trusted }">
        <van-icon :name="trusted ? 'checked' : 'info-o'" />
        {{ trusted ? "HTTPS 已连接，可以继续配对" : "检测成功后才能安全获取库存数据" }}
      </div>

      <div class="pair-card surface">
        <h2>第二步：输入配对码</h2>
        <p>在电脑“系统设置 → 手机配对”中生成，有效期 5 分钟。</p>
        <van-field v-model="deviceName" label="设备名称" placeholder="例如：仓库手机" />
        <van-field v-model="code" label="配对码" maxlength="6" type="digit" placeholder="6 位数字" />
        <van-progress v-if="pairing" :percentage="progress" stroke-width="8" />
        <p v-if="pairing" class="progress-copy">{{ progressText || "正在登记设备…" }}</p>
        <van-button
          block
          type="primary"
          class="primary-action"
          :disabled="!trusted"
          :loading="pairing"
          @click="pair"
        >
          配对并初始化
        </van-button>
      </div>
      <p class="risk-copy">
        安装本地 CA 意味着本机信任由这台电脑签发的证书。CA 私钥不出电脑、不进入备份包；不再使用时可从系统设置删除。
      </p>
    </div>
  </section>
</template>

<style scoped>
.setup-page { min-height: 100vh; background: #f4f7fb; }
.setup-header { min-height: 88px; padding: max(16px, env(safe-area-inset-top)) 18px 16px; display: flex; gap: 12px; align-items: center; color: white; background: linear-gradient(125deg, #052947, #075184); }
.setup-header button { width: 36px; height: 36px; border: 0; border-radius: 50%; color: white; background: rgb(255 255 255 / 12%); }
.setup-header strong, .setup-header span { display: block; }
.setup-header strong { font-size: 20px; }
.setup-header span { margin-top: 5px; font-size: 11px; opacity: .75; }
.setup-content { padding: 14px 14px 36px; }
.trust-card { margin-bottom: 12px; padding: 14px; display: flex; gap: 12px; align-items: center; border-radius: 12px; color: #0b3c67; background: #e9f3ff; }
.trust-card > .van-icon { font-size: 26px; }
.trust-card strong, .trust-card span { display: block; }
.trust-card span { margin-top: 3px; font-size: 11px; color: #64788f; }
.android-title { margin: 15px 2px 8px; font-size: 15px; }
.guide-list { margin: 12px 0; padding: 0; list-style: none; }
.guide-list li { display: grid; grid-template-columns: 30px 1fr; gap: 10px; margin-bottom: 8px; padding: 10px 12px; border-radius: 10px; background: white; }
.guide-list li > span { width: 26px; height: 26px; display: grid; place-items: center; border-radius: 50%; color: white; background: var(--blue); font-weight: 700; }
.guide-list strong { font-size: 13px; }
.guide-list p { margin: 4px 0 0; color: var(--muted); font-size: 11px; line-height: 1.5; }
.download-button { height: 46px; display: flex; align-items: center; justify-content: center; gap: 7px; border-radius: 10px; color: #116de7; background: #eaf3ff; font-weight: 700; text-decoration: none; }
.url-note, .risk-copy { color: #7a899b; font-size: 10px; line-height: 1.55; overflow-wrap: anywhere; }
.detect-result { margin: 8px 0 18px; color: #8491a1; font-size: 11px; text-align: center; }
.detect-result.success { color: #18834a; }
.pair-card { padding: 16px; }
.pair-card h2 { margin: 0; font-size: 17px; }
.pair-card > p { margin: 5px 0 12px; color: var(--muted); font-size: 11px; }
.pair-card :deep(.van-cell) { margin-bottom: 8px; border: 1px solid #d6dfeb; border-radius: 9px; }
.progress-copy { text-align: center; }
</style>
