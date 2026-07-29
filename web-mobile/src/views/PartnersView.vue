<script setup lang="ts">
import { computed, onActivated, onMounted, ref } from "vue";
import { db, type NamedRow } from "../db/schema";

type PartnerKind = "customer" | "supplier";

const active = ref<PartnerKind>("customer");
const keyword = ref("");
const customers = ref<NamedRow[]>([]);
const suppliers = ref<NamedRow[]>([]);
const rows = computed(() => {
  const source = active.value === "customer" ? customers.value : suppliers.value;
  const needle = keyword.value.trim().toLowerCase();
  return source
    .filter((row) => row.is_deleted === 0 && row.is_active === 1)
    .filter((row) =>
      [row.name, row.phone, row.contact, row.address, row.location]
        .filter(Boolean)
        .some((value) => String(value).toLowerCase().includes(needle)),
    )
    .sort((a, b) => a.name.localeCompare(b.name, "zh-CN"));
});

function value(row: NamedRow, key: string): string {
  const result = row[key];
  return typeof result === "string" ? result : "";
}

async function load(): Promise<void> {
  [customers.value, suppliers.value] = await Promise.all([
    db.customers.toArray(),
    db.suppliers.toArray(),
  ]);
}

onMounted(load);
onActivated(load);
</script>

<template>
  <section class="page partners-page">
    <van-tabs v-model:active="active" shrink>
      <van-tab title="客户" name="customer" />
      <van-tab title="供应商" name="supplier" />
    </van-tabs>
    <van-search
      v-model="keyword"
      shape="round"
      background="transparent"
      :placeholder="`搜索${active === 'customer' ? '客户' : '供应商'}、电话或地址`"
    />

    <div class="contact-count">共 {{ rows.length }} 个{{ active === "customer" ? "客户" : "供应商" }}</div>
    <div v-if="rows.length" class="contact-list">
      <article v-for="row in rows" :key="row.id" class="surface contact-card">
        <div class="contact-avatar">{{ row.name.slice(0, 1) }}</div>
        <div class="contact-main">
          <strong>{{ row.name }}</strong>
          <span v-if="value(row, 'contact')">联系人：{{ value(row, "contact") }}</span>
          <span v-if="value(row, 'phone')">{{ value(row, "phone") }}</span>
          <small v-if="value(row, 'address') || value(row, 'location')">
            {{ value(row, "address") || value(row, "location") }}
          </small>
        </div>
        <a
          v-if="value(row, 'phone')"
          class="phone-action"
          :href="`tel:${value(row, 'phone')}`"
          aria-label="拨打电话"
        >
          <van-icon name="phone-o" />
        </a>
      </article>
    </div>
    <div v-else class="surface empty-state">
      <strong>暂无匹配联系人</strong>
      客户与供应商资料会在同步后保存在本机。
    </div>
    <p class="offline-note">通讯录来自本机离线数据，拨号前由手机系统再次确认。</p>
  </section>
</template>

<style scoped>
.partners-page :deep(.van-tabs__nav) { padding: 0; background: transparent; }
.partners-page :deep(.van-tabs__line) { background: var(--blue); }
.partners-page :deep(.van-search) { padding: 12px 0 5px; }
.partners-page :deep(.van-search__content) { border: 1px solid #d0dae6; background: white; }
.contact-count { padding: 8px 2px 10px; color: var(--muted); font-size: 11px; }
.contact-list { display: grid; gap: 10px; }
.contact-card {
  display: grid;
  grid-template-columns: 42px minmax(0, 1fr) 42px;
  align-items: center;
  gap: 12px;
  padding: 14px;
}
.contact-avatar {
  width: 42px;
  height: 42px;
  display: grid;
  place-items: center;
  border-radius: 12px;
  color: #1765d4;
  background: #eaf3ff;
  font-size: 17px;
  font-weight: 750;
}
.contact-main strong,
.contact-main span,
.contact-main small { display: block; }
.contact-main strong { font-size: 15px; }
.contact-main span { margin-top: 5px; color: #53657c; font-size: 12px; }
.contact-main small { margin-top: 5px; color: var(--muted); line-height: 1.45; }
.phone-action {
  width: 40px;
  height: 40px;
  display: grid;
  place-items: center;
  border-radius: 50%;
  color: white;
  background: #198754;
  font-size: 20px;
  text-decoration: none;
}
.offline-note { color: var(--muted); font-size: 11px; line-height: 1.6; text-align: center; }
</style>
