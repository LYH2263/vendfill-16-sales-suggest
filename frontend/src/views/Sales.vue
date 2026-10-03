<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { api, generateRefillOrder } from '../api'

const sales = ref<any[]>([])
const preview = ref<any>(null)
const message = ref('')
const error = ref('')
const busy = ref(false)

const STATUS_LABEL: Record<string, string> = { need_fill: '待补', full: '满仓', overbooked: '超占' }

async function load() {
  // 每次进入销量页都按现网缺口现算建议列
  sales.value = await api('/sales')
  preview.value = await api('/refills/preview?location_id=1')
}

async function generate() {
  busy.value = true
  message.value = ''
  error.value = ''
  try {
    const order = await generateRefillOrder(1)
    message.value = `补货单 #${order.id} 已生成，共 ${order.total_fill} 件`
  } catch (e: any) {
    error.value = e.message || '生成失败'
  } finally {
    busy.value = false
    // 无论成败都刷新建议列：成功后与单一致，失败后跟上最新缺口
    preview.value = await api('/refills/preview?location_id=1')
  }
}

onMounted(load)
</script>

<template>
  <h1>销量</h1>
  <p class="sub">建议补量按现网缺口现算（只读）· 点生成即以提交瞬间的建议落单</p>

  <div class="card">
    <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:0.75rem">
      <strong>补货建议</strong>
      <button class="btn" :disabled="busy" @click="generate">生成补货单</button>
    </div>
    <p v-if="message" style="color:var(--vf-led);margin:0 0 0.5rem">{{ message }}</p>
    <p v-if="error" style="color:var(--vf-red);margin:0 0 0.5rem">{{ error }}</p>
    <table v-if="preview">
      <thead>
        <tr><th>货道</th><th>商品</th><th>库存</th><th>在途</th><th>容量</th><th>缺口</th><th>建议补量</th><th>状态</th></tr>
      </thead>
      <tbody>
        <tr v-for="l in preview.lines" :key="l.lane_id">
          <td>{{ l.slot_no }}</td>
          <td>{{ l.sku_name }}</td>
          <td>{{ l.stock }}</td>
          <td>{{ l.in_transit }}</td>
          <td>{{ l.capacity }}</td>
          <td>{{ l.gap }}</td>
          <td><strong>{{ l.fill_qty }}</strong></td>
          <td>{{ STATUS_LABEL[l.status] ?? l.status }}</td>
        </tr>
      </tbody>
      <tfoot>
        <tr>
          <td colspan="6" style="text-align:right"><strong>建议总件数</strong></td>
          <td colspan="2"><strong>{{ preview.total_fill }}</strong></td>
        </tr>
      </tfoot>
    </table>
  </div>

  <div class="card" style="margin-top:1rem">
    <strong>近期出货</strong>
    <table style="margin-top:0.5rem">
      <thead><tr><th>货道</th><th>商品</th><th>数量</th><th>时间</th></tr></thead>
      <tbody>
        <tr v-for="r in sales" :key="r.id ?? JSON.stringify(r)"><td>{{ r.slot_no }}</td><td>{{ r.sku_name }}</td><td>{{ r.qty }}</td><td>{{ r.sold_at }}</td></tr>
      </tbody>
    </table>
  </div>
</template>
