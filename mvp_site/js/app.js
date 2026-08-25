import { DatasetRepository } from "./data.js";
import { LabelingGame, needsAllNoConfirmation } from "./game.js";
import { LocalStorageAnnotationStore } from "./storage.js";
import { AppUI } from "./ui.js";
import { getBadges, getNextMilestone } from "./dashboard.js";
import { ACTIVITY_NOTICES, getEngagementStats, getWeeklyStats } from "./engagement.js";
import { createConfiguredSupabaseClient } from "./supabase.js";
import { SupabaseAnnotationSync } from "./supabase-store.js";

export const APP_CONFIG = Object.freeze({
  candidatesPerQuestion: 10,
  debug: false,
  appVersion: "mvp-1",
});

const repository = new DatasetRepository();
const store = new LocalStorageAnnotationStore();
const supabase = createConfiguredSupabaseClient();
const game = new LabelingGame(repository, store, APP_CONFIG);
const ui = new AppUI(APP_CONFIG);
let authUser = null;
let remoteSync = null;
let recentlyDiscoveredFish = new Set();
let leaderboardPeriod = "all";

function authDisplayName(user) {
  return user?.user_metadata?.full_name
    || user?.user_metadata?.name
    || user?.email?.split("@")[0]
    || "Google 使用者";
}

function setAuthenticatedHeader(authenticated) {
  document.querySelector("#signout-button").hidden = !authenticated;
  document.querySelector("#dashboard-nav").hidden = !authenticated && !game.profile;
}

function mergeRemoteAnnotations(records) {
  if (typeof store.mergeAnnotationBatch === "function") {
    store.mergeAnnotationBatch(records);
    return;
  }
  // Compatibility with a browser tab that still has an older storage module cached.
  const existing = store.getAnnotations();
  const keys = new Set(existing.map((item) => `${item.annotator_id}:${item.dataset_id}:${item.fish_id}:${item.candidate_id}`));
  const additions = records.filter((item) => {
    const key = `${item.annotator_id}:${item.dataset_id}:${item.fish_id}:${item.candidate_id}`;
    if (keys.has(key)) return false;
    keys.add(key);
    return true;
  });
  store.saveAnnotationBatch(additions);
}

async function prepareRemoteSync(dataset) {
  if (!supabase || !authUser) return;
  const candidateSync = new SupabaseAnnotationSync(supabase, authUser.id);
  try {
    const remoteAnnotations = await candidateSync.prepare(dataset);
    mergeRemoteAnnotations(remoteAnnotations);
    remoteSync = candidateSync;
  } catch (error) {
    remoteSync = null;
    console.error("Supabase 標註同步初始化失敗：", error);
    ui.showToast(`Supabase 標註尚未同步：${error.message}`);
  }
}

async function syncRemoteIdentity() {
  if (!remoteSync || !game.profile || !game.session) return;
  try {
    await remoteSync.syncIdentity(game.profile, game.session, game.dataset);
  } catch (error) {
    console.error("Supabase 使用者資料同步失敗：", error);
    ui.showToast("帳號已登入，但個人資料尚未同步到 Supabase。");
  }
}

function profileStats() {
  return game.profile ? store.getStats(game.profile.annotator_id, game.dataset?.dataset_id) : { images: 0, questions: 0 };
}

function dashboardProgress() {
  return store.getDatasetProgress(game.profile.annotator_id, game.dataset);
}

function engagementStats() {
  const annotations = store.getDatasetAnnotations(game.profile.annotator_id, game.dataset.dataset_id);
  return getEngagementStats(annotations);
}

function recentActivities() {
  const annotations = store.getDatasetAnnotations(game.profile.annotator_id, game.dataset.dataset_id);
  const questions = new Map();
  for (const annotation of annotations) {
    if (!annotation.question_batch_id || questions.has(annotation.question_batch_id)) continue;
    questions.set(annotation.question_batch_id, annotation);
  }
  const recent = [...questions.values()]
    .sort((a, b) => String(b.created_at).localeCompare(String(a.created_at)))
    .slice(0, 5)
    .map((item) => ({
      icon: "✅",
      title: `完成「${item.canonical_name || "魚類"}」一題`,
      copy: `${new Date(item.created_at).toLocaleString("zh-TW", { dateStyle: "short", timeStyle: "short" })} · 已協助判斷一組候選圖片`,
    }));
  return [...ACTIVITY_NOTICES, ...recent];
}

function showDashboard() {
  if (!game.profile || !game.dataset) return;
  ui.setDashboardTab("overview");
  const progress = dashboardProgress();
  const annotations = store.getDatasetAnnotations(game.profile.annotator_id, game.dataset.dataset_id);
  const nearComplete = progress.byFish.filter((fish) => fish.total - fish.completed > 0 && fish.total - fish.completed <= 5);
  ui.renderDashboard(
    game.profile, progress, getBadges(progress), engagementStats(), getNextMilestone(progress), recentActivities(), getWeeklyStats(annotations), nearComplete, recentlyDiscoveredFish,
  );
  ui.renderLeaderboard([], { enabled: Boolean(remoteSync), period: leaderboardPeriod });
  if (remoteSync) {
    remoteSync.getLeaderboard(game.dataset.dataset_id, leaderboardPeriod)
      .then((rows) => ui.renderLeaderboard(rows, { enabled: true, period: leaderboardPeriod }))
      .catch((error) => ui.renderLeaderboard([], { enabled: false, period: leaderboardPeriod }));
  }
}

function openFishPicker() {
  const dialog = document.querySelector("#fish-picker-dialog");
  const search = document.querySelector("#fish-picker-search");
  const options = document.querySelector("#fish-picker-options");
  const submit = document.querySelector("#fish-picker-submit");
  let selectedFishId = null;
  const fish = [...new Map((game.dataset.tasks || []).map((task) => [task.fish_id, task])).values()];
  const renderOptions = () => {
    const keyword = search.value.trim().toLocaleLowerCase();
    options.replaceChildren(...fish.filter((task) => `${task.canonical_name} ${(task.aliases || []).join(" ")}`.toLocaleLowerCase().includes(keyword)).map((task) => {
      const button = document.createElement("button");
      button.type = "button";
      button.className = `fish-picker-option${selectedFishId === task.fish_id ? " selected" : ""}`;
      button.dataset.fishId = task.fish_id;
      button.setAttribute("role", "option");
      button.setAttribute("aria-selected", String(selectedFishId === task.fish_id));
      button.innerHTML = `<strong>${task.canonical_name}</strong><span>${(task.aliases || []).join("、") || ""}</span>`;
      return button;
    }));
  };
  search.value = "";
  submit.disabled = true;
  renderOptions();
  options.onclick = (event) => {
    const option = event.target.closest("[data-fish-id]");
    if (!option) return;
    selectedFishId = option.dataset.fishId;
    submit.disabled = false;
    renderOptions();
  };
  search.oninput = renderOptions;
  dialog.querySelector('[data-fish-mode="random"]').onclick = () => {
    game.setFishSelection(null);
    dialog.close("random");
    showNextQuestion();
  };
  dialog.querySelector('[data-fish-mode="specific"]').onclick = () => search.focus();
  submit.onclick = (event) => {
    if (!selectedFishId) { event.preventDefault(); return; }
    game.setFishSelection(selectedFishId);
    dialog.close("confirm");
    setTimeout(() => showNextQuestion(), 0);
  };
  dialog.showModal();
}

async function showNextQuestion() {
  try {
    const question = await game.nextQuestion();
    if (!question) {
      ui.renderCompletion(profileStats());
      return;
    }
    ui.renderQuestion(question, profileStats(), game.dataset, (candidateId, judgment) => {
      game.setJudgment(candidateId, judgment);
      ui.updateSelectionSummary(game.question.selections);
    });
  } catch (error) {
    console.error(error);
    ui.showError(`候選圖片資料無法載入。${error.message}`);
  }
}

async function initialize() {
  ui.showScreen("loading-screen");
  try {
    if (supabase) {
      const { data, error } = await supabase.auth.getSession();
      if (error) console.warn("Supabase Auth 尚未完成設定：", error.message);
      authUser = data?.session?.user || null;
    }
    const state = await game.initialize();
    await prepareRemoteSync(state.dataset);
    if (!state.dataset.tasks.length) {
      ui.renderCompletion({ images: 0, questions: 0 });
      ui.showToast("目前載入的資料集沒有可用題目，請查看資料準備警告。");
      return;
    }
    if (store.corruptionNotices.length) ui.showToast("偵測到損壞的本機資料，已備份並安全復原。可匯出 JSON 查看備份內容。");
    if (supabase && !authUser && !store.corruptionNotices.length) ui.showToast("Supabase 設定已載入；可使用 Google 登入。");
    if (!state.profile && authUser) {
      game.start(authDisplayName(authUser), { annotatorId: authUser.id });
      await syncRemoteIdentity();
      setAuthenticatedHeader(true);
      showDashboard();
      return;
    }
    if (!authUser) {
      ui.showScreen("landing-screen");
      document.querySelector("#google-login-button").hidden = !supabase;
      if (!supabase) ui.showToast("目前尚未設定 Supabase，無法登入與提交標註。");
      return;
    }
    if (!state.profile || state.profile.annotator_id !== authUser.id) {
      game.start(authDisplayName(authUser), { annotatorId: authUser.id });
    } else if (!game.session) game.start(state.profile.display_name);
    await syncRemoteIdentity();
    setAuthenticatedHeader(true);
    showDashboard();
  } catch (error) {
    console.error(error);
    ui.showError(`無法讀取 data/index.json。請確認已執行準備腳本，並透過本機 HTTP 伺服器開啟。詳細資訊：${error.message}`);
  }
}

document.querySelector("#google-login-button").addEventListener("click", async () => {
  if (!supabase) {
    ui.showToast("尚未載入 Supabase 設定，請聯絡網站管理者。");
    return;
  }
  const redirectTo = `${window.location.origin}${window.location.pathname}`;
  const { error } = await supabase.auth.signInWithOAuth({
    provider: "google",
    options: { redirectTo },
  });
  if (error) ui.showToast(`Google 登入失敗：${error.message}`);
});

document.querySelector("#submit-question").addEventListener("click", async () => {
  if (!authUser) {
    ui.showToast("請先使用 Google 登入，再開始標註。");
    ui.showScreen("landing-screen");
    return;
  }
  if (!game.question) return;
  if (needsAllNoConfirmation(game.question)) {
    const confirmed = await ui.confirm({
      title: "確認全部都不包含？",
      message: `你沒有選取任何圖片。\n確定這些圖片都不是「${game.question.target.canonical_name}」嗎？`,
      confirmText: "確定，全部都不是",
    });
    if (!confirmed) return;
  }
  const unlockedBefore = new Set(getBadges(dashboardProgress()).filter((badge) => badge.unlocked).map((badge) => badge.id));
  const discoveredBefore = new Set(dashboardProgress().byFish.filter((fish) => fish.completed > 0).map((fish) => fish.fish_id));
  const dailyWasComplete = engagementStats().dailyComplete;
  const records = game.submit();
  const count = records.length;
  let remoteSyncFailed = false;
  let remoteSyncErrorMessage = "";
  if (remoteSync) {
    try {
      await remoteSync.saveAnnotationBatch(records);
    } catch (error) {
      remoteSyncFailed = true;
      remoteSyncErrorMessage = error.message;
      console.error("Supabase 標註同步失敗：", error);
    }
  }
  const newlyUnlocked = getBadges(dashboardProgress()).filter((badge) => badge.unlocked && !unlockedBefore.has(badge.id));
  recentlyDiscoveredFish = new Set(dashboardProgress().byFish.filter((fish) => fish.completed > 0 && !discoveredBefore.has(fish.fish_id)).map((fish) => fish.fish_id));
  const dailyIsComplete = engagementStats().dailyComplete;
  ui.showToast(remoteSyncFailed
    ? `本機已記錄，但尚未同步到 Supabase：${remoteSyncErrorMessage}`
    : !dailyWasComplete && dailyIsComplete
    ? "今日 10 題挑戰完成！🔥"
    : recentlyDiscoveredFish.size
      ? `發現新魚種「${[...recentlyDiscoveredFish].map((id) => dashboardProgress().byFish.find((fish) => fish.fish_id === id)?.canonical_name).filter(Boolean).join("、")}」！`
      : newlyUnlocked.length
      ? `解鎖勳章「${newlyUnlocked[0].name}」${newlyUnlocked.length > 1 ? `，另有 ${newlyUnlocked.length - 1} 枚新勳章` : ""}！`
      : `已記錄 ${count} 張圖片，謝謝你的幫忙！`);
  await showNextQuestion();
});

function download(content, mime, filename) {
  const blob = new Blob([content], { type: mime });
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = filename;
  document.body.append(anchor);
  anchor.click();
  anchor.remove();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}

document.addEventListener("click", async (event) => {
  const dashboardTab = event.target.closest("[data-dashboard-tab]")?.dataset.dashboardTab;
  if (dashboardTab) {
    ui.setDashboardTab(dashboardTab);
    return;
  }
  const leaderboardButton = event.target.closest("[data-leaderboard-period]");
  if (leaderboardButton) {
    leaderboardPeriod = leaderboardButton.dataset.leaderboardPeriod;
    document.querySelectorAll("[data-leaderboard-period]").forEach((button) => button.classList.toggle("active", button === leaderboardButton));
    if (remoteSync) {
      ui.renderLeaderboard([], { enabled: true, period: leaderboardPeriod });
      remoteSync.getLeaderboard(game.dataset.dataset_id, leaderboardPeriod)
        .then((rows) => ui.renderLeaderboard(rows, { enabled: true, period: leaderboardPeriod }))
        .catch(() => ui.renderLeaderboard([], { enabled: false, period: leaderboardPeriod }));
    }
    return;
  }
  const action = event.target.closest("[data-action]")?.dataset.action;
  if (!action) return;
  document.querySelector(".utility-menu")?.removeAttribute("open");
  const date = new Date().toISOString().slice(0, 10);
  if (action === "dashboard") {
    showDashboard();
  } else if (action === "badges") {
    const panel = document.querySelector("#badge-panel");
    const button = event.target.closest("[data-action=badges]");
    const expanded = panel.hidden;
    panel.hidden = !expanded;
    button.setAttribute("aria-expanded", String(expanded));
    button.firstChild.textContent = expanded ? "收起我的勳章 " : "查看我的勳章 ";
  } else if (action === "continue-labeling") {
    openFishPicker();
  } else if (action === "signout") {
    if (supabase) await supabase.auth.signOut();
    authUser = null;
    remoteSync = null;
    location.reload();
  } else if (action === "export-csv") {
    download(store.exportAnnotations("csv", game.dataset), "text/csv;charset=utf-8", `fish-annotations-${date}.csv`);
  } else if (action === "export-json") {
    download(store.exportAnnotations("json", game.dataset), "application/json;charset=utf-8", `fish-annotations-${date}.json`);
  } else if (action === "reset") {
    const confirmed = await ui.confirm({
      title: "重設本機資料？",
      message: "這會清除這個版本在本機儲存的個人資料、目前題目與所有標註。建議先匯出資料。",
      confirmText: "確定重設",
      cancelText: "取消",
    });
    if (confirmed) { store.resetAppData(); location.reload(); }
  }
});

document.querySelector("#retry-button").addEventListener("click", () => location.reload());

initialize();
