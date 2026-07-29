<script setup lang="ts">
import { onMounted, ref } from "vue";
import { useRouter } from "vue-router";
import { getMeta } from "../db/schema";
import { useAppStore } from "../stores/app";

const router = useRouter();
const appStore = useAppStore();
const deviceName = ref("未配对");
const initializedAt = ref<string | null>(null);
onMounted(async () => {
  deviceName.value = (await getMeta("device_name")) || "未配对";
  initializedAt.value = await getMeta("initialized_at");
});
</script>

<template>
  <section class="page profile-page">
    <div class="profile-hero">
      <div class="avatar"><van-icon name="contact-o" /></div>
      <div><strong>{{ deviceName }}</strong><span>AutoStock 移动端</span></div>
    </div>
    <div class="surface profile-list">
      <div><span>初始化状态</span><strong>{{ initializedAt ? "已完成" : "未完成" }}</strong></div>
      <div><span>待同步记录</span><strong>{{ appStore.pendingCount }} 笔</strong></div>
      <div><span>上次同步</span><strong>{{ appStore.lastSyncAt?.replace("T", " ").slice(0, 16) || "暂无" }}</strong></div>
    </div>
    <h2 class="section-title">连接与安全</h2>
    <div class="surface action-list">
      <button type="button" @click="router.push('/contacts')">
        <van-icon name="friends-o" /><span><strong>客户与供应商</strong><small>离线查看联系人、地址并快速拨号</small></span><van-icon name="arrow" />
      </button>
      <button type="button" @click="router.push('/sync')">
        <van-icon name="exchange" /><span><strong>同步中心</strong><small>立即同步、查看结果与失败记录</small></span><van-icon name="arrow" />
      </button>
      <button type="button" @click="router.push('/setup')">
        <van-icon name="scan" /><span><strong>重新配对或初始化</strong><small>电脑 IP 变动时可重新扫描配对码</small></span><van-icon name="arrow" />
      </button>
      <button type="button" @click="router.push('/setup?guide=1')">
        <van-icon name="shield-o" /><span><strong>证书安装引导</strong><small>Android CA 安装与 Chrome 主屏幕步骤</small></span><van-icon name="arrow" />
      </button>
    </div>
    <p class="security-note">
      本地 CA 私钥只保存在你的电脑中。停止使用后，可在手机系统设置中删除 AutoStock Local CA。
    </p>
  </section>
</template>

<style scoped>
.profile-hero { display: flex; gap: 13px; align-items: center; padding: 12px 4px 22px; }
.avatar { width: 52px; height: 52px; display: grid; place-items: center; border-radius: 16px; color: white; background: linear-gradient(135deg, #0b3c67, #1677ff); font-size: 27px; }
.profile-hero strong, .profile-hero span { display: block; }
.profile-hero strong { font-size: 18px; }
.profile-hero span { margin-top: 5px; color: var(--muted); font-size: 12px; }
.profile-list div { display: flex; justify-content: space-between; padding: 15px 16px; border-bottom: 1px solid #edf1f5; }
.profile-list div:last-child { border-bottom: 0; }
.profile-list span { color: var(--muted); }
.profile-list strong { font-size: 13px; }
.action-list button { width: 100%; padding: 15px; display: grid; grid-template-columns: 28px 1fr 18px; align-items: center; border: 0; border-bottom: 1px solid #edf1f5; color: #253951; background: white; text-align: left; }
.action-list button:last-child { border-bottom: 0; }
.action-list button > .van-icon:first-child { color: var(--blue); font-size: 20px; }
.action-list strong, .action-list small { display: block; }
.action-list small { margin-top: 5px; color: var(--muted); }
.security-note { padding: 10px 5px; color: #77869a; font-size: 11px; line-height: 1.6; }
</style>
