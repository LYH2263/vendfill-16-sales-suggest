<script setup lang="ts">
import { onMounted, reactive, ref } from 'vue'
import { api } from '../api'
const rows = ref<any[]>([])
const suggest = ref<any>(null)
const edit = reactive<Record<number, { stock: number; in_transit: number }>>({})
const saving = ref<number | null>(null)
const msg = ref('')
const msgOk = ref(false)

async function load() {
  rows.value = await api('/lanes')
  for (const r of rows.value) edit[r.id] = { stock: r.stock, in_transit: r.in_transit }
  suggest.value = await api('/refills/suggest?location_id=1')
}
async function save(id: number) {
  if (saving.value !== null) return
  saving.value = id
  msg.value = ''
  try {
    await api(`/lanes/${id}`, { method: 'PATCH', body: JSON.stringify(edit[id]) })
    await load()
    msg.value = '已保存，建议已按新缺口重算'
    msgOk.value = true
  } catch (e: any) {
    msg.value = `保存失败：${e.message}`
    msgOk.value = false
  } finally {
    saving.value = null
  }
}
onMounted(load)
</script>
<template>
  <h1>货道格子</h1>
  <p class="sub">机面货道网格 · 可改库存/在途 · 右侧为现算建议预览（不落单）</p>
  <p v-if="msg" :style="{ color: msgOk ? 'var(--vf-led)' : 'var(--vf-red)' }" style="margin:0 0 0.6rem;font-size:0.8rem">{{ msg }}</p>
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
        <div class="vf-slot-edit" v-if="edit[r.id]">
          <label>存<input type="number" min="0" v-model.number="edit[r.id].stock" /></label>
          <label>途<input type="number" min="0" v-model.number="edit[r.id].in_transit" /></label>
          <button class="vf-slot-save" :disabled="saving === r.id" @click="save(r.id)">保存</button>
        </div>
      </div>
    </div>
    <aside class="vf-receipt" v-if="suggest">
      <h2>*** 补货建议预览 ***</h2>
      <div class="vf-receipt-line" v-for="l in suggest.lines" :key="l.lane_id">
        <span>{{ l.slot_no }} {{ l.sku_name }}</span>
        <span>x{{ l.fill_qty }}</span>
      </div>
      <p class="muted" style="margin:0.75rem 0 0;font-size:0.72rem;color:#6a5e48;text-align:center">
        — 现算预览 · 未落单 · 共 {{ suggest.total_fill }} 件 —
      </p>
    </aside>
  </div>
</template>
