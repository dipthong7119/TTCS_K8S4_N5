/**
 * Maps every item through an async function, a bounded number of them in
 * flight at once, and resolves to the results in the items' order.
 *
 * @param items the inputs
 * @param limit how many may run at once, at least one
 * @param fn the work for one item
 * @returns the results, in order
 */
export async function mapLimited<T, R>(
  items: readonly T[],
  limit: number,
  fn: (item: T) => Promise<R>,
): Promise<R[]> {
  const results: R[] = []

  let next = 0

  async function worker(): Promise<void> {
    for (let at = next++; at < items.length; at = next++) {
      results[at] = await fn(items[at] as T)
    }
  }

  await Promise.all(
    Array.from({ length: Math.max(1, Math.min(limit, items.length)) }, worker),
  )

  return results
}
