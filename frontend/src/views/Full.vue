<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { api } from '../api'
const lanes = ref<any[]>([])
onMounted(async () => { lanes.value = (await api('/refills/full?location_id=1')).lanes })
</script>
<template>
  <h1>满仓</h1>
  <p class="sub">最近一张补货单中缺口为 0 的货道（无需补货）</p>
  <div class="card">
    <p v-if="!lanes.length" class="muted" style="margin:0">暂无满仓货道（或尚未生成补货单）</p>
    <table v-else>
      <thead><tr><th>货道</th><th>商品</th><th>库存</th><th>在途</th><th>容量</th></tr></thead>
      <tbody>
        <tr v-for="l in lanes" :key="l.lane_id">
          <td>{{ l.slot_no }}</td><td>{{ l.sku_name }}</td><td>{{ l.stock }}</td><td>{{ l.in_transit }}</td><td>{{ l.capacity }}</td>
        </tr>
      </tbody>
    </table>
  </div>
</template>
