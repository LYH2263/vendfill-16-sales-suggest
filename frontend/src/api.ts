export async function api<T = any>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch('/api' + path, {
    headers: { 'Content-Type': 'application/json', ...(init?.headers || {}) },
    ...init,
  })
  if (!res.ok) {
    let msg = res.statusText
    try {
      const data = await res.json()
      if (data?.detail) msg = typeof data.detail === 'string' ? data.detail : JSON.stringify(data.detail)
    } catch { /* 保留 statusText */ }
    throw new Error(msg)
  }
  if (res.status === 204) return undefined as T
  return res.json()
}

/** 生成补货单：点击瞬间重新现算建议，并带该快照落单。
 *  若取数与提交之间库存/在途又被改过，后端返回 409「建议已过期」，整次不落单。 */
export async function generateRefillOrder(locationId = 1): Promise<any> {
  const fresh = await api(`/refills/preview?location_id=${locationId}`)
  const expected = fresh.lines.map((l: any) => ({ lane_id: l.lane_id, fill_qty: l.fill_qty }))
  return api(`/refills/run?location_id=${locationId}`, {
    method: 'POST',
    body: JSON.stringify({ expected }),
  })
}
