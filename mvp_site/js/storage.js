export const STORAGE_KEYS = Object.freeze({
  profile: "fish_labeler_mvp_v1_profile",
  annotations: "fish_labeler_mvp_v1_annotations",
  currentQuestion: "fish_labeler_mvp_v1_current_question",
  sessions: "fish_labeler_mvp_v1_sessions",
  recoveryPrefix: "fish_labeler_mvp_v1_corrupt_",
});

export function createId(prefix = "") {
  const value = globalThis.crypto?.randomUUID?.() || `${Date.now()}-${Math.random().toString(16).slice(2)}`;
  return `${prefix}${value}`;
}

function csvCell(value) {
  const text = value == null ? "" : String(value);
  return /[",\r\n]/.test(text) ? `"${text.replaceAll('"', '""')}"` : text;
}

export function annotationsToCsv(annotations) {
  const columns = [
    "annotation_id", "session_id", "annotator_id", "display_name", "target_id", "fish_id",
    "canonical_name", "reference_filename", "candidate_id", "candidate_image_url",
    "candidate_source_page_url", "judgment", "position", "question_batch_id", "dataset_id",
    "created_at", "app_version",
  ];
  const rows = [columns.join(",")];
  for (const annotation of annotations) {
    rows.push(columns.map((column) => csvCell(annotation[column])).join(","));
  }
  return `\ufeff${rows.join("\r\n")}\r\n`;
}

export class AnnotationStore {
  getAnnotatorProfile() { throw new Error("Not implemented"); }
  saveAnnotatorProfile() { throw new Error("Not implemented"); }
  saveAnnotationBatch() { throw new Error("Not implemented"); }
  getAnnotations() { throw new Error("Not implemented"); }
  getLabeledCandidateIds() { throw new Error("Not implemented"); }
  getCurrentQuestion() { throw new Error("Not implemented"); }
  saveCurrentQuestion() { throw new Error("Not implemented"); }
  clearCurrentQuestion() { throw new Error("Not implemented"); }
}

export class LocalStorageAnnotationStore extends AnnotationStore {
  constructor(storage = globalThis.localStorage) {
    super();
    this.storage = storage;
    this.corruptionNotices = [];
  }

  _read(key, fallback) {
    const raw = this.storage.getItem(key);
    if (raw == null) return fallback;
    try {
      return JSON.parse(raw);
    } catch (error) {
      const recoveryKey = `${STORAGE_KEYS.recoveryPrefix}${Date.now()}_${key.slice(-18)}`;
      try { this.storage.setItem(recoveryKey, raw); } catch { /* storage may be full */ }
      this.storage.removeItem(key);
      this.corruptionNotices.push({ key, recoveryKey, raw, message: String(error) });
      return fallback;
    }
  }

  _write(key, value) { this.storage.setItem(key, JSON.stringify(value)); }
  getAnnotatorProfile() { return this._read(STORAGE_KEYS.profile, null); }
  saveAnnotatorProfile(profile) { this._write(STORAGE_KEYS.profile, profile); }
  getAnnotations() {
    const value = this._read(STORAGE_KEYS.annotations, []);
    return Array.isArray(value) ? value : [];
  }
  saveAnnotationBatch(records) {
    if (!Array.isArray(records) || !records.length) return;
    this._write(STORAGE_KEYS.annotations, [...this.getAnnotations(), ...records]);
  }
  mergeAnnotationBatch(records) {
    if (!Array.isArray(records) || !records.length) return;
    const existing = this.getAnnotations();
    const keys = new Set(existing.map((item) => `${item.annotator_id}:${item.dataset_id}:${item.fish_id}:${item.candidate_id}`));
    const additions = records.filter((item) => {
      const key = `${item.annotator_id}:${item.dataset_id}:${item.fish_id}:${item.candidate_id}`;
      if (keys.has(key)) return false;
      keys.add(key);
      return true;
    });
    if (additions.length) this._write(STORAGE_KEYS.annotations, [...existing, ...additions]);
  }
  getLabeledCandidateIds(annotatorId, fishId, datasetId = null) {
    return new Set(this.getAnnotations()
      .filter((item) => item.annotator_id === annotatorId
        && item.fish_id === fishId
        && (!datasetId || item.dataset_id === datasetId))
      .map((item) => item.candidate_id));
  }
  getCurrentQuestion() { return this._read(STORAGE_KEYS.currentQuestion, null); }
  saveCurrentQuestion(question) { this._write(STORAGE_KEYS.currentQuestion, question); }
  clearCurrentQuestion() { this.storage.removeItem(STORAGE_KEYS.currentQuestion); }
  getSessions() {
    const value = this._read(STORAGE_KEYS.sessions, []);
    return Array.isArray(value) ? value : [];
  }
  startSession(profile, datasetId) {
    const session = {
      session_id: createId("session_"), annotator_id: profile.annotator_id,
      display_name: profile.display_name, dataset_id: datasetId, started_at: new Date().toISOString(),
    };
    this._write(STORAGE_KEYS.sessions, [...this.getSessions(), session]);
    return session;
  }
  getStats(annotatorId, datasetId = null) {
    const annotations = this.getAnnotations().filter((item) => item.annotator_id === annotatorId
      && (!datasetId || item.dataset_id === datasetId));
    return {
      images: new Set(annotations.map((item) => `${item.fish_id}:${item.candidate_id}`)).size,
      questions: new Set(annotations.map((item) => item.question_batch_id)).size,
    };
  }
  getDatasetProgress(annotatorId, dataset) {
    const annotations = this.getAnnotations().filter((item) => item.annotator_id === annotatorId
      && item.dataset_id === dataset.dataset_id);
    const fish = new Map();
    for (const task of dataset.tasks || []) {
      const current = fish.get(task.fish_id);
      if (!current) {
        fish.set(task.fish_id, {
          fish_id: task.fish_id,
          canonical_name: task.canonical_name,
          reference_image: task.reference_image,
          candidate_count: Number(task.candidate_count) || 0,
          completed: new Set(),
        });
      } else {
        current.candidate_count = Math.max(current.candidate_count, Number(task.candidate_count) || 0);
      }
    }
    for (const item of annotations) {
      const entry = fish.get(item.fish_id);
      if (entry && item.candidate_id) entry.completed.add(item.candidate_id);
    }
    const byFish = [...fish.values()].map((entry) => ({
      fish_id: entry.fish_id,
      canonical_name: entry.canonical_name,
      reference_image: entry.reference_image,
      completed: entry.completed.size,
      total: entry.candidate_count,
      percent: entry.candidate_count ? Math.min(100, entry.completed.size / entry.candidate_count * 100) : 0,
    })).sort((left, right) => right.percent - left.percent || left.canonical_name.localeCompare(right.canonical_name, "zh-Hant"));
    const completed = byFish.reduce((sum, item) => sum + item.completed, 0);
    const total = Number(dataset.candidate_count) || byFish.reduce((sum, item) => sum + item.total, 0);
    const judgments = { yes: 0, no: 0, unsure: 0, broken: 0 };
    annotations.forEach((item) => { if (item.judgment in judgments) judgments[item.judgment] += 1; });
    return {
      completed,
      total,
      percent: total ? Math.min(100, completed / total * 100) : 0,
      questions: new Set(annotations.map((item) => item.question_batch_id)).size,
      judgments,
      byFish,
    };
  }
  getDatasetAnnotations(annotatorId, datasetId) {
    return this.getAnnotations().filter((item) => item.annotator_id === annotatorId
      && item.dataset_id === datasetId);
  }
  buildExportPayload(dataset) {
    return {
      schema_version: 1,
      app_version: "mvp-1",
      exported_at: new Date().toISOString(),
      dataset: dataset ? {
        dataset_id: dataset.dataset_id,
        generated_at: dataset.generated_at,
        task_count: dataset.task_count,
        candidate_count: dataset.candidate_count,
      } : null,
      profile: this.getAnnotatorProfile(),
      sessions: this.getSessions(),
      annotations: this.getAnnotations(),
      recovered_corrupt_data: this.corruptionNotices,
    };
  }
  exportAnnotations(format, dataset) {
    if (format === "csv") return annotationsToCsv(this.getAnnotations());
    return JSON.stringify(this.buildExportPayload(dataset), null, 2);
  }
  resetAppData() {
    const keys = [];
    for (let index = 0; index < this.storage.length; index += 1) keys.push(this.storage.key(index));
    for (const key of keys) {
      if (key && (Object.values(STORAGE_KEYS).includes(key) || key.startsWith(STORAGE_KEYS.recoveryPrefix))) {
        this.storage.removeItem(key);
      }
    }
  }
}
