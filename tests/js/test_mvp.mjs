import assert from "node:assert/strict";
import test from "node:test";
import { buildAnnotationRecords, LabelingGame, needsAllNoConfirmation, sampleUnseenCandidates } from "../../mvp_site/js/game.js";
import { annotationsToCsv, LocalStorageAnnotationStore } from "../../mvp_site/js/storage.js";
import { getBadges, getNextMilestone } from "../../mvp_site/js/dashboard.js";
import { getEngagementStats } from "../../mvp_site/js/engagement.js";

class MemoryStorage {
  constructor() { this.values = new Map(); }
  get length() { return this.values.size; }
  key(index) { return [...this.values.keys()][index] ?? null; }
  getItem(key) { return this.values.has(key) ? this.values.get(key) : null; }
  setItem(key, value) { this.values.set(key, String(value)); }
  removeItem(key) { this.values.delete(key); }
}

const target = {
  target_id: "target-1", fish_id: "fish_001", canonical_name: "紅紋笛鯛", aliases: ["赤筆"],
  reference_filename: "photo.jpg", reference_image: "photo.webp", candidate_file: "fish.json", candidate_count: 4,
};
const candidates = [1, 2, 3, 4].map((value) => ({
  candidate_id: `cand-${value}`, image_url: `https://img/${value}.jpg`, source_page_url: `https://source/${value}`,
}));

test("sampling excludes labeled candidates and never duplicates", () => {
  const sampled = sampleUnseenCandidates([...candidates, candidates[0]], new Set(["cand-2"]), 10, () => 0.5);
  assert.equal(sampled.length, 3);
  assert.equal(new Set(sampled.map((item) => item.candidate_id)).size, sampled.length);
  assert.ok(!sampled.some((item) => item.candidate_id === "cand-2"));
});

test("judgments serialize as yes, no, unsure, and broken", () => {
  const question = {
    target, candidates, question_batch_id: "batch", selections: { "cand-1": "yes", "cand-3": "unsure", "cand-4": "broken" },
  };
  const records = buildAnnotationRecords(
    question, { annotator_id: "annotator", display_name: "Amy" }, { session_id: "session" }, "dataset",
    new Date("2026-01-01T00:00:00Z"),
  );
  assert.deepEqual(records.map((item) => item.judgment), ["yes", "no", "unsure", "broken"]);
  const csv = annotationsToCsv(records);
  for (const judgment of ["yes", "no", "unsure", "broken"]) assert.match(csv, new RegExp(`,${judgment},`));
  assert.ok(csv.startsWith("\ufeff"));
});

test("current question survives a new store instance", () => {
  const storage = new MemoryStorage();
  const first = new LocalStorageAnnotationStore(storage);
  const question = { dataset_id: "dataset", target, candidates, selections: { "cand-1": "yes" } };
  first.saveCurrentQuestion(question);
  assert.deepEqual(new LocalStorageAnnotationStore(storage).getCurrentQuestion(), question);
});

test("all-NO confirmation is needed only with no active labels", () => {
  assert.equal(needsAllNoConfirmation({ selections: {} }), true);
  assert.equal(needsAllNoConfirmation({ selections: { "cand-1": "yes" } }), false);
  assert.equal(needsAllNoConfirmation({ selections: { "cand-1": "unsure" } }), false);
  assert.equal(needsAllNoConfirmation({ selections: { "cand-1": "broken" } }), false);
});

test("game returns completion when every local candidate is exhausted", async () => {
  const storage = new MemoryStorage();
  const store = new LocalStorageAnnotationStore(storage);
  const profile = { annotator_id: "annotator", display_name: "Amy" };
  store.saveAnnotatorProfile(profile);
  store.saveAnnotationBatch(candidates.map((candidate) => ({
    annotator_id: "annotator", fish_id: "fish_001", candidate_id: candidate.candidate_id, dataset_id: "dataset",
  })));
  const repository = {
    loadIndex: async () => ({ dataset_id: "dataset", tasks: [target] }),
    loadCandidatePool: async () => ({ fish_id: "fish_001", candidates }),
  };
  const game = new LabelingGame(repository, store);
  await game.initialize();
  game.start("Amy");
  assert.equal(await game.nextQuestion(), null);
});

test("old annotations do not hide new candidates with the same fish ID", async () => {
  const storage = new MemoryStorage();
  const store = new LocalStorageAnnotationStore(storage);
  store.saveAnnotatorProfile({ annotator_id: "annotator", display_name: "Amy" });
  store.saveAnnotationBatch(candidates.map((candidate, index) => ({
    annotator_id: "annotator", fish_id: "fish_001", candidate_id: `obsolete-${index}`,
  })));
  const repository = {
    loadIndex: async () => ({ dataset_id: "new-dataset", tasks: [target] }),
    loadCandidatePool: async () => ({ fish_id: "fish_001", candidates }),
  };
  const game = new LabelingGame(repository, store, { random: () => 0.5 });
  await game.initialize();
  game.start("Amy");
  assert.equal((await game.nextQuestion()).candidates.length, 4);
});

test("dataset progress counts unique candidates per fish and ignores old datasets", () => {
  const storage = new MemoryStorage();
  const store = new LocalStorageAnnotationStore(storage);
  store.saveAnnotationBatch([
    { annotator_id: "annotator", fish_id: "fish_001", candidate_id: "cand-1", dataset_id: "dataset", question_batch_id: "q1", judgment: "yes" },
    { annotator_id: "annotator", fish_id: "fish_001", candidate_id: "cand-1", dataset_id: "dataset", question_batch_id: "q1", judgment: "yes" },
    { annotator_id: "annotator", fish_id: "fish_001", candidate_id: "cand-2", dataset_id: "old", question_batch_id: "old", judgment: "no" },
  ]);
  const progress = store.getDatasetProgress("annotator", {
    dataset_id: "dataset", candidate_count: 4, tasks: [target],
  });
  assert.equal(progress.completed, 1);
  assert.equal(progress.total, 4);
  assert.equal(progress.percent, 25);
  assert.equal(progress.questions, 1);
  assert.equal(progress.byFish[0].completed, 1);
  assert.equal(progress.judgments.yes, 2);
});

test("badges unlock from derived progress", () => {
  const badges = getBadges({
    completed: 50, total: 100, questions: 5,
    byFish: [{ completed: 10 }, { completed: 20 }, { completed: 20 }],
  });
  assert.deepEqual(badges.filter((badge) => badge.unlocked).map((badge) => badge.id), [
    "first_dive", "sharp_eye", "species_scout",
  ]);
  assert.equal(getNextMilestone({
    completed: 50, total: 100, questions: 5,
    byFish: [{ completed: 10 }, { completed: 20 }, { completed: 20 }],
  }).id, "century");
});

test("daily challenge counts rounds and streak includes consecutive local days", () => {
  const annotations = [];
  for (let question = 1; question <= 10; question += 1) {
    for (let image = 0; image < 10; image += 1) {
      annotations.push({ question_batch_id: `today-${question}`, created_at: "2026-08-25T02:00:00.000Z", candidate_id: `${question}-${image}` });
    }
  }
  annotations.push(
    { question_batch_id: "yesterday", created_at: "2026-08-24T02:00:00.000Z" },
    { question_batch_id: "two-days-ago", created_at: "2026-08-23T02:00:00.000Z" },
  );
  const engagement = getEngagementStats(annotations, new Date("2026-08-25T04:00:00.000Z"));
  assert.equal(engagement.todayQuestions, 10);
  assert.equal(engagement.dailyComplete, true);
  assert.equal(engagement.streak, 3);
  assert.equal(engagement.activeDays, 3);
});

test("streak remains visible before participating today", () => {
  const engagement = getEngagementStats([
    { question_batch_id: "yesterday", created_at: "2026-08-24T02:00:00.000Z" },
    { question_batch_id: "two-days-ago", created_at: "2026-08-23T02:00:00.000Z" },
  ], new Date("2026-08-25T04:00:00.000Z"));
  assert.equal(engagement.todayQuestions, 0);
  assert.equal(engagement.streak, 2);
});
