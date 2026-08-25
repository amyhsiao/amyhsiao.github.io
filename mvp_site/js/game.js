import { createId } from "./storage.js";

export const JUDGMENTS = Object.freeze(["yes", "no", "unsure", "broken"]);

export function shuffle(items, random = Math.random) {
  const result = [...items];
  for (let index = result.length - 1; index > 0; index -= 1) {
    const swap = Math.floor(random() * (index + 1));
    [result[index], result[swap]] = [result[swap], result[index]];
  }
  return result;
}

export function sampleUnseenCandidates(candidates, labeledIds, limit, random = Math.random) {
  const unique = new Map();
  for (const candidate of candidates) {
    if (candidate?.candidate_id && !labeledIds.has(candidate.candidate_id)) unique.set(candidate.candidate_id, candidate);
  }
  return shuffle([...unique.values()], random).slice(0, limit);
}

export function buildAnnotationRecords(question, profile, session, datasetId, now = new Date()) {
  const createdAt = now.toISOString();
  return question.candidates.map((candidate, index) => ({
    annotation_id: createId("annotation_"),
    session_id: session.session_id,
    annotator_id: profile.annotator_id,
    display_name: profile.display_name,
    target_id: question.target.target_id,
    fish_id: question.target.fish_id,
    canonical_name: question.target.canonical_name,
    reference_filename: question.target.reference_filename,
    candidate_id: candidate.candidate_id,
    candidate_image_url: candidate.image_url || candidate.thumbnail_url || "",
    candidate_source_page_url: candidate.source_page_url || "",
    judgment: question.selections[candidate.candidate_id] || "no",
    position: index + 1,
    question_batch_id: question.question_batch_id,
    dataset_id: datasetId,
    created_at: createdAt,
    app_version: "mvp-1",
  }));
}

export function needsAllNoConfirmation(question) {
  return Boolean(question) && Object.keys(question.selections || {}).length === 0;
}

export class LabelingGame {
  constructor(repository, store, { candidatesPerQuestion = 10, random = Math.random } = {}) {
    this.repository = repository;
    this.store = store;
    this.candidatesPerQuestion = candidatesPerQuestion;
    this.random = random;
    this.dataset = null;
    this.profile = null;
    this.session = null;
    this.question = null;
    this.fishSelection = null;
  }

  async initialize() {
    this.dataset = await this.repository.loadIndex();
    this.profile = this.store.getAnnotatorProfile();
    const saved = this.store.getCurrentQuestion();
    if (saved?.dataset_id === this.dataset.dataset_id && Array.isArray(saved.candidates) && saved.target) {
      this.question = saved;
      this.session = saved.session;
    } else if (saved) {
      this.store.clearCurrentQuestion();
    }
    return { dataset: this.dataset, profile: this.profile, question: this.question };
  }

  start(displayName, { annotatorId = null } = {}) {
    const previous = this.store.getAnnotatorProfile();
    this.profile = {
      annotator_id: annotatorId || previous?.annotator_id || createId("annotator_"),
      display_name: displayName.trim(),
      updated_at: new Date().toISOString(),
    };
    this.store.saveAnnotatorProfile(this.profile);
    if (!this.session || this.session.annotator_id !== this.profile.annotator_id) {
      this.session = this.store.startSession(this.profile, this.dataset.dataset_id);
    }
    return this.profile;
  }

  setFishSelection(fishId = null) {
    this.fishSelection = fishId || null;
    this.question = null;
    this.store.clearCurrentQuestion();
  }

  async nextQuestion() {
    if (this.question) return this.question;
    const tasks = this.dataset.tasks || [];
    const tasksByFish = new Map();
    for (const task of tasks) {
      if (!tasksByFish.has(task.fish_id)) tasksByFish.set(task.fish_id, []);
      tasksByFish.get(task.fish_id).push(task);
    }
    const selectedGroups = this.fishSelection
      ? [...tasksByFish.entries()].filter(([fishId]) => fishId === this.fishSelection)
      : [...tasksByFish.entries()];
    const fishGroups = shuffle(selectedGroups, this.random);
    const loadErrors = [];
    for (const [fishId, fishTasks] of fishGroups) {
      const labeledIds = this.store.getLabeledCandidateIds(
        this.profile.annotator_id, fishId, this.dataset.dataset_id,
      );
      const target = shuffle(fishTasks, this.random)[0];
      try {
        const pool = await this.repository.loadCandidatePool(target);
        const candidates = sampleUnseenCandidates(pool.candidates, labeledIds, this.candidatesPerQuestion, this.random);
        if (!candidates.length) continue;
        this.question = {
          schema_version: 1,
          dataset_id: this.dataset.dataset_id,
          question_batch_id: createId("question_"),
          created_at: new Date().toISOString(),
          target,
          candidates,
          selections: {},
          session: this.session,
        };
        this.store.saveCurrentQuestion(this.question);
        return this.question;
      } catch (error) {
        loadErrors.push(`${fishId}: ${error.message}`);
      }
    }
    if (loadErrors.length === fishGroups.length && fishGroups.length) {
      throw new Error(`候選資料皆無法載入：${loadErrors.join("；")}`);
    }
    return null;
  }

  setJudgment(candidateId, judgment) {
    if (!this.question || !["yes", "unsure", "broken", null].includes(judgment)) return;
    if (judgment === null) delete this.question.selections[candidateId];
    else this.question.selections[candidateId] = judgment;
    this.store.saveCurrentQuestion(this.question);
  }

  hasActiveLabels() { return Object.keys(this.question?.selections || {}).length > 0; }

  submit() {
    const records = buildAnnotationRecords(
      this.question, this.profile, this.session, this.dataset.dataset_id,
    );
    this.store.saveAnnotationBatch(records);
    this.store.clearCurrentQuestion();
    this.question = null;
    return records;
  }
}
