<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { api } from '../api'

const rows = ref<any[]>([])
const preview = ref<any>(null)
const edit = ref<Record<number, { stock: number; in_transit: number }>>({})
const message = ref('')
const error = ref('')

async function load() {
  rows.value = await api('/lanes')
  preview.value = await api('/refills/preview?location_id=1')
  const m: Record<number, { stock: number; in_transit: number }> = {}
  for (const r of rows.value) m[r.id] = { stock: r.stock, in_transit: r.in_transit }
  edit.value = m
}

async function save(id: number) {
  message.value = ''
  error.value = ''
  try {
    await api(`/lanes/${id}`, { method: 'PATCH', body: JSON.stringify(edit.value[id]) })
    message.value = `货道 #${id} 已保存`
    await load()
  } catch (e: any) {
    error.value = e.message || '保存失败'
  }
}

onMounted(load)
</script>

<template>
  <h1>货道格子</h1>
  <p class="sub">机面货道网格 · 格内库存条 · 右侧补货小票</p>
  <div class="vf-machine-layout">
    <div class="vf-slot-grid">
      <div v-for="r in rows" :key="r.id" class="vf-slot">
        <div class="vf-slot-no">{{ r.slot_no }}</div>
        <div class="vf-slot-sku">{{ r.sku_name }}</div>
        <div class="vf-slot-bar">
          <div
            class="vf-slot-fill"
            :class="{ 'vf-need': r.gap > 0 }"
            :style="{ width: Math.min(r.fill_pct, 100) + '%' }"
          />
        </div>
        <div class="vf-slot-meta">{{ r.stock }}/{{ r.capacity }} · 缺 {{ r.gap }}</div>
      </div>
    </div>
    <aside class="vf-receipt" v-if="preview">
      <h2>*** 补货建议单 ***</h2>
      <div class="vf-receipt-line" v-for="l in preview.lines" :key="l.lane_id">
        <span>{{ l.slot_no }} {{ l.sku_name }}</span>
        <span>x{{ l.fill_qty }}</span>
      </div>
      <p class="muted" style="margin:0.75rem 0 0;font-size:0.72rem;color:#6a5e48;text-align:center">
        — 机面打印预览 —
      </p>
    </aside>
  </div>

  <div class="card" style="margin-top:1rem">
    <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:0.5rem">
      <strong>货道改数（库存 / 在途）</strong>
      <span v-if="message" style="color:var(--vf-led);font-size:0.8rem">{{ message }}</span>
      <span v-if="error" style="color:var(--vf-red);font-size:0.8rem">{{ error }}</span>
    </div>
    <table>
      <thead><tr><th>货道</th><th>商品</th><th>容量</th><th>库存</th><th>在途</th><th>缺口</th><th></th></tr></thead>
      <tbody>
        <tr v-for="r in rows" :key="r.id">
          <td>{{ r.slot_no }}</td>
          <td>{{ r.sku_name }}</td>
          <td>{{ r.capacity }}</td>
          <td><input v-model.number="edit[r.id].stock" type="number" min="0" style="width:5rem" /></td>
          <td><input v-model.number="edit[r.id].in_transit" type="number" min="0" style="width:5rem" /></td>
          <td>{{ r.gap }}</td>
          <td><button class="btn" style="padding:0.2rem 0.6rem" @click="save(r.id)">保存</button></td>
        </tr>
      </tbody>
    </table>
  </div>
</template>
