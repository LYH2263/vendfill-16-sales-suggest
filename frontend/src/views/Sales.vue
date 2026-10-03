<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { api } from '../api'

const sales = ref<any[]>([])
const sug = ref<any>(null)
const msg = ref('')
const msgOk = ref(false)
const busy = ref(false)

// 建议补量列、汇总总件数、满仓名单来自同一份现算数据，天然对账
const fullLanes = computed(() => (sug.value?.lines ?? []).filter((l: any) => l.status === 'full'))

async function refreshSuggest() {
  sug.value = await api('/refills/suggest?location_id=1')
}
async function generate() {
  if (busy.value) return
  busy.value = true
  msg.value = ''
  try {
    // 不带任何页上数值：落单量由后端按提交瞬间缺口重算
    const order = await api('/refills/run?location_id=1', { method: 'POST' })
    msg.value = `已生成补货单 #${order.id} · 共 ${order.total_fill} 件（按提交瞬间缺口落单）`
    msgOk.value = true
  } catch (e: any) {
    msg.value = `生成失败：${e.message}`
    msgOk.value = false
  } finally {
    busy.value = false
    await refreshSuggest()
  }
}
onMounted(() => { refreshSuggest(); api('/sales').then(r => (sales.value = r)) })
</script>
<template>
  <h1>销量</h1>
  <p class="sub">建议补量按现网缺口现算 · 建议列只读 · 生成时以提交瞬间缺口落单</p>

  <div class="card">
    <div style="display:flex;align-items:center;gap:1.25rem;flex-wrap:wrap">
      <button class="btn" :disabled="busy" @click="generate">生成补货单</button>
      <div>汇总总件数：<span class="stat" style="font-size:1.2rem">{{ sug ? sug.total_fill : '—' }}</span></div>
      <div class="muted" v-if="sug">待补 {{ sug.need_fill_count }} · 满仓 {{ sug.full_count }} · 超占 {{ sug.overbooked_count }}</div>
    </div>
    <p v-if="msg" :style="{ color: msgOk ? 'var(--vf-led)' : 'var(--vf-red)' }" style="margin:0.5rem 0 0;font-size:0.8rem">{{ msg }}</p>
  </div>

  <div class="card" v-if="sug">
    <table>
      <thead><tr><th>货道</th><th>商品</th><th>库存</th><th>在途</th><th>容量</th><th>缺口</th><th>建议补量</th></tr></thead>
      <tbody>
        <tr v-for="l in sug.lines" :key="l.lane_id">
          <td>{{ l.slot_no }}</td><td>{{ l.sku_name }}</td>
          <td>{{ l.stock }}</td><td>{{ l.in_transit }}</td><td>{{ l.capacity }}</td>
          <td>{{ l.gap }}</td>
          <td>
            <span class="badge" :class="l.status === 'need_fill' ? 'badge-warn' : l.status === 'full' ? 'badge-ok' : 'badge-bad'">{{ l.fill_qty }}</span>
          </td>
        </tr>
      </tbody>
    </table>
  </div>

  <div class="card">
    <strong>满仓名单</strong>
    <span v-if="!fullLanes.length" class="muted"> · 暂无满仓货道</span>
    <span v-for="l in fullLanes" :key="l.lane_id" class="badge badge-ok" style="margin-left:0.4rem">{{ l.slot_no }} {{ l.sku_name }}</span>
  </div>

  <div class="card">
    <p class="sub" style="margin-bottom:0.5rem">近期出货记录</p>
    <table>
      <thead><tr><th>货道</th><th>商品</th><th>数量</th><th>时间</th></tr></thead>
      <tbody>
        <tr v-for="r in sales" :key="r.id ?? JSON.stringify(r)"><td>{{ r.slot_no }}</td><td>{{ r.sku_name }}</td><td>{{ r.qty }}</td><td>{{ r.sold_at }}</td></tr>
      </tbody>
    </table>
  </div>
</template>
