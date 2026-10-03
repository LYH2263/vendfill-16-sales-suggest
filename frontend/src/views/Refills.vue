<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { api } from '../api'
const data = ref<any>(null)
const isOrder = ref(false)
const msg = ref('')
const busy = ref(false)

async function load() {
  try {
    data.value = await api('/refills/latest?location_id=1')
    isOrder.value = true
  } catch {
    data.value = await api('/refills/suggest?location_id=1')
    isOrder.value = false
  }
}
async function run() {
  if (busy.value) return
  busy.value = true
  msg.value = ''
  try {
    data.value = await api('/refills/run?location_id=1', { method: 'POST' })
    isOrder.value = true
  } catch (e: any) {
    msg.value = `生成失败：${e.message}`
  } finally {
    busy.value = false
  }
}
onMounted(load)
</script>
<template>
  <h1>补货小票</h1>
  <p class="sub">gap = 容量 − 库存 − 在途 · 收据纸样式</p>
  <button class="btn" :disabled="busy" @click="run">生成补货单</button>
  <span v-if="msg" style="margin-left:0.75rem;color:var(--vf-red);font-size:0.8rem">{{ msg }}</span>
  <div style="margin-top:1rem" v-if="data">
    <div class="vf-receipt">
      <h2>{{ isOrder ? `*** VendFill 补货单 #${data.id} ***` : '*** 补货建议预览（未落单） ***' }}</h2>
      <div class="vf-receipt-line" style="font-weight:700;border-bottom:2px dashed #8a7e64">
        <span>货道 / 商品</span><span>补量</span>
      </div>
      <div class="vf-receipt-line" v-for="l in data.lines" :key="l.lane_id">
        <span>{{ l.slot_no }} {{ l.sku_name }}
          <small>({{ l.status === 'need_fill' ? '待补' : l.status === 'full' ? '满仓' : '超占' }})</small>
        </span>
        <span>{{ l.fill_qty }} / 缺{{ l.gap }}</span>
      </div>
      <p style="text-align:center;margin:1rem 0 0;font-size:0.72rem;color:#6a5e48">
        {{ isOrder ? `共 ${data.total_fill} 件 · 谢谢使用 · 请核对后装机` : `共 ${data.total_fill} 件 · 现算预览 · 点生成落单` }}
      </p>
    </div>
  </div>
</template>
