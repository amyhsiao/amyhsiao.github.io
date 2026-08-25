export class DatasetRepository {
  constructor(indexUrl = "data/index.json", fetchImpl = globalThis.fetch.bind(globalThis)) {
    this.indexUrl = indexUrl;
    this.fetchImpl = fetchImpl;
    this.index = null;
    this.poolCache = new Map();
  }

  async loadIndex() {
    const response = await this.fetchImpl(this.indexUrl, { cache: "no-cache" });
    if (!response.ok) throw new Error(`index.json 回應 ${response.status}`);
    const index = await response.json();
    if (!index || !Array.isArray(index.tasks) || !index.dataset_id) {
      throw new Error("index.json 格式不正確");
    }
    this.index = index;
    return index;
  }

  async loadCandidatePool(task) {
    if (this.poolCache.has(task.fish_id)) return this.poolCache.get(task.fish_id);
    const promise = this.fetchImpl(task.candidate_file).then(async (response) => {
      if (!response.ok) throw new Error(`${task.fish_id} 候選資料回應 ${response.status}`);
      const pool = await response.json();
      if (!pool || pool.fish_id !== task.fish_id || !Array.isArray(pool.candidates)) {
        throw new Error(`${task.fish_id} 候選資料格式不正確`);
      }
      return pool;
    });
    this.poolCache.set(task.fish_id, promise);
    try {
      return await promise;
    } catch (error) {
      this.poolCache.delete(task.fish_id);
      throw error;
    }
  }
}
