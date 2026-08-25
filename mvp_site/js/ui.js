const stateLabels = { neutral: "未選取", yes: "✓ 包含" };

export class AppUI {
  constructor({ debug = false } = {}) {
    this.debug = debug;
    this.screens = [...document.querySelectorAll("main > .screen")];
    this.grid = document.querySelector("#candidate-grid");
    this.toastTimer = null;
  }

  showScreen(id) {
    for (const screen of this.screens) screen.hidden = screen.id !== id;
    document.querySelector(`#${id}`)?.querySelector("h1, input, button")?.focus({ preventScroll: true });
  }

  showError(message) {
    document.querySelector("#error-message").textContent = message;
    this.showScreen("error-screen");
  }

  showToast(message) {
    const toast = document.querySelector("#toast");
    toast.textContent = message;
    toast.hidden = false;
    clearTimeout(this.toastTimer);
    this.toastTimer = setTimeout(() => { toast.hidden = true; }, 3200);
  }

  setDashboardTab(tab = "overview") {
    document.querySelectorAll("[data-dashboard-page]").forEach((page) => {
      page.hidden = page.dataset.dashboardPage !== tab;
    });
    document.querySelectorAll("[data-dashboard-tab]").forEach((button) => {
      const active = button.dataset.dashboardTab === tab;
      button.classList.toggle("active", active);
      button.setAttribute("aria-selected", String(active));
    });
  }

  renderLeaderboard(rows = [], { enabled = false, period = "all" } = {}) {
    const message = document.querySelector("#leaderboard-message");
    const list = document.querySelector("#leaderboard-list");
    message.textContent = enabled ? (rows.length ? `目前顯示${period === "week" ? "本週" : "全部時間"}前 20 名` : "目前還沒有排行榜資料，完成第一題就能上榜！") : "登入 Google 後即可查看共同排行榜。";
    list.replaceChildren(...rows.map((row) => {
      const item = document.createElement("div");
      item.className = "leaderboard-row";
      const rank = document.createElement("strong");
      rank.textContent = `#${row.rank}`;
      const name = document.createElement("span");
      name.textContent = row.display_name;
      const count = document.createElement("b");
      count.textContent = `${Number(row.label_count).toLocaleString("zh-TW")} 張`;
      item.append(rank, name, count);
      return item;
    }));
  }

  renderQuestion(question, stats, dataset, onChange) {
    const { target } = question;
    document.querySelector("#fish-name").textContent = target.canonical_name;
    document.querySelector("#fish-name-inline").textContent = target.canonical_name;
    const alias = document.querySelector("#fish-aliases");
    alias.textContent = target.aliases?.length ? `別名：${target.aliases.join("、")}` : "";
    const reference = document.querySelector("#reference-image");
    const referenceError = document.querySelector("#reference-error");
    reference.hidden = false;
    referenceError.hidden = true;
    reference.src = target.reference_image;
    reference.alt = `${target.canonical_name}的參考照片`;
    reference.onerror = () => { reference.hidden = true; referenceError.hidden = false; };

    this.grid.replaceChildren();
    question.candidates.forEach((candidate, index) => {
      this.grid.append(this.createCandidateCard(candidate, index, question.selections[candidate.candidate_id], onChange));
    });
    const debugPanel = document.querySelector("#debug-task");
    debugPanel.hidden = !this.debug;
    if (this.debug) debugPanel.textContent = `dataset_id: ${dataset.dataset_id}\nfish_id: ${target.fish_id}\ntarget_id: ${target.target_id}\nquestion_batch_id: ${question.question_batch_id}`;
    this.renderStats(stats, dataset);
    this.updateSelectionSummary(question.selections);
    this.showScreen("game-screen");
  }

  createCandidateCard(candidate, index, initialState, onChange) {
    const card = document.createElement("article");
    card.className = "candidate-card";
    card.dataset.candidateId = candidate.candidate_id;
    const select = document.createElement("button");
    select.type = "button";
    select.className = "candidate-select";
    select.setAttribute("aria-label", `候選圖片 ${index + 1}：切換是否包含目標魚種`);
    select.innerHTML = `<span class="candidate-number" aria-hidden="true">${index + 1}</span><span class="state-badge"></span>`;
    const image = document.createElement("img");
    image.alt = `候選圖片 ${index + 1}`;
    image.loading = "lazy";
    image.decoding = "async";
    image.referrerPolicy = "no-referrer";
    select.prepend(image);
    card.append(select);

    const actions = document.createElement("div");
    actions.className = "candidate-actions";
    const source = document.createElement("a");
    source.textContent = "查看來源";
    // Keep the source page as the primary link; direct original image is the
    // fallback. The card itself starts with the lighter thumbnail below.
    source.href = candidate.source_page_url || candidate.image_url || candidate.thumbnail_url || "#";
    source.target = "_blank";
    source.rel = "noopener noreferrer";
    source.setAttribute("aria-label", `在新分頁查看候選圖片 ${index + 1} 的來源`);
    if (!candidate.source_page_url && !candidate.image_url && !candidate.thumbnail_url) source.hidden = true;
    actions.append(source);
    card.append(actions);
    if (this.debug) {
      const debug = document.createElement("div");
      debug.className = "candidate-debug";
      debug.textContent = `${candidate.candidate_id}\n${candidate.source_domain || ""}\n${candidate.image_url || candidate.thumbnail_url}`;
      card.append(debug);
    }

    const applyState = (state, notify = true) => {
      const normalized = state || "neutral";
      card.dataset.state = normalized;
      card.querySelector(".state-badge").textContent = stateLabels[normalized];
      select.setAttribute("aria-pressed", String(normalized === "yes"));
      select.setAttribute("aria-label", `候選圖片 ${index + 1}：${normalized === "yes" ? "取消包含標記" : "標記為包含"}`);
      if (notify) onChange(candidate.candidate_id, normalized === "neutral" ? null : normalized);
    };
    select.addEventListener("click", () => applyState(card.dataset.state === "yes" ? null : "yes"));
    applyState(initialState, false);

    const urls = [...new Set([candidate.thumbnail_url, candidate.image_url].filter(Boolean))];
    let urlIndex = 0;
    const placeholder = document.createElement("span");
    placeholder.className = "candidate-placeholder";
    placeholder.textContent = "圖片無法載入";
    placeholder.hidden = true;
    select.append(placeholder);
    image.addEventListener("error", () => {
      urlIndex += 1;
      if (urlIndex < urls.length) image.src = urls[urlIndex];
      else {
        image.hidden = true;
        placeholder.hidden = false;
      }
    });
    if (urls.length) image.src = urls[0];
    else {
      image.hidden = true;
      placeholder.hidden = false;
      applyState(null, false);
    }
    return card;
  }

  actionButton(text, label) {
    const button = document.createElement("button");
    button.type = "button";
    button.textContent = text;
    button.setAttribute("aria-label", label);
    button.setAttribute("aria-pressed", "false");
    return button;
  }

  updateCardState(candidateId, state) {
    const card = [...this.grid.children].find((item) => item.dataset.candidateId === candidateId);
    if (!card) return;
    // Card event handling already renders its state; this method updates only the summary.
  }

  updateSelectionSummary(selections) {
    const counts = { yes: 0 };
    Object.values(selections).forEach((state) => { if (state in counts) counts[state] += 1; });
    const parts = [];
    if (counts.yes) parts.push(`包含 ${counts.yes}`);
    document.querySelector("#selection-summary").textContent = parts.length ? parts.join(" · ") : "尚未選取；送出後皆記為不包含";
  }

  renderStats(stats, dataset) {
    document.querySelector("#question-count").textContent = stats.questions.toLocaleString("zh-TW");
    document.querySelector("#image-count").textContent = stats.images.toLocaleString("zh-TW");
    const denominator = Math.max(1, Number(dataset.candidate_count) || 1);
    document.querySelector("#progress-bar").style.width = `${Math.min(100, stats.images / denominator * 100)}%`;
  }

  renderDashboard(profile, progress, badges, engagement, milestone, activities = [], weekly = null, nearComplete = [], discoveredFish = new Set()) {
    document.querySelector("#dashboard-name").textContent = profile.display_name;
    const roundedPercent = Math.round(progress.percent);
    document.querySelector("#dashboard-percent").textContent = `${roundedPercent}%`;
    document.querySelector("#dashboard-completed").textContent = progress.completed.toLocaleString("zh-TW");
    document.querySelector("#dashboard-total").textContent = progress.total.toLocaleString("zh-TW");
    document.querySelector("#dashboard-questions").textContent = progress.questions.toLocaleString("zh-TW");
    document.querySelector("#dashboard-species").textContent = progress.byFish.filter((fish) => fish.completed > 0).length.toLocaleString("zh-TW");
    document.querySelector("#dashboard-yes").textContent = progress.judgments.yes.toLocaleString("zh-TW");
    document.querySelector("#dashboard-label-button").textContent = progress.completed ? "繼續辨識" : "開始辨識";
    document.querySelector("#dashboard-progress-bar").style.width = `${progress.percent}%`;
    const ring = document.querySelector("#dashboard-progress-ring");
    ring.style.setProperty("--progress", `${progress.percent * 3.6}deg`);
    ring.setAttribute("aria-label", `整體完成 ${roundedPercent}%`);

    document.querySelector("#today-questions").textContent = Math.min(engagement.todayQuestions, engagement.dailyTarget).toLocaleString("zh-TW");
    document.querySelector("#daily-progress-bar").style.width = `${engagement.dailyPercent}%`;
    document.querySelector("#daily-challenge-message").textContent = engagement.dailyComplete
      ? "今日挑戰完成！明天再一起回來探索。"
      : engagement.todayQuestions
        ? `再完成 ${engagement.dailyTarget - engagement.todayQuestions} 題即可達成今日挑戰。`
        : "今天一起完成第一題吧。";
    document.querySelector("#streak-days").textContent = engagement.streak.toLocaleString("zh-TW");
    document.querySelector("#active-days-copy").textContent = `累積參與 ${engagement.activeDays.toLocaleString("zh-TW")} 天`;
    if (weekly) {
      document.querySelector("#weekly-questions").textContent = weekly.completed.toLocaleString("zh-TW");
      document.querySelector("#weekly-progress-bar").style.width = `${weekly.percent}%`;
      document.querySelector("#weekly-task-message").textContent = weekly.complete ? "本週任務完成！下週繼續挑戰。" : `再完成 ${weekly.target - weekly.completed} 題即可完成本週任務。`;
    }
    const milestoneIcon = document.querySelector("#milestone-icon");
    const milestoneName = document.querySelector("#milestone-name");
    const milestoneCopy = document.querySelector("#milestone-copy");
    const milestoneBar = document.querySelector("#milestone-progress-bar");
    if (milestone) {
      milestoneIcon.textContent = milestone.icon;
      milestoneName.textContent = milestone.name;
      milestoneCopy.textContent = `再完成 ${milestone.remaining} ${milestone.unit}即可解鎖`;
      milestoneBar.style.width = `${milestone.percent}%`;
    } else {
      milestoneIcon.textContent = "🏆";
      milestoneName.textContent = "所有里程碑已完成";
      milestoneCopy.textContent = "你已完成目前資料集的所有成就！";
      milestoneBar.style.width = "100%";
    }

    const activityFeed = document.querySelector("#activity-feed");
    activityFeed.replaceChildren(...(activities.length ? activities : [{
      icon: "📣", title: "活動公告會顯示在這裡", copy: "未來的抽獎、限時挑戰與社群消息都可以放在這個彈性窗口。",
    }]).map((activity) => {
      const item = document.createElement("article");
      item.className = "activity-item";
      const icon = document.createElement("span");
      icon.className = "activity-item-icon";
      icon.textContent = activity.icon || "📌";
      icon.setAttribute("aria-hidden", "true");
      const content = document.createElement("div");
      const title = document.createElement("strong");
      title.textContent = activity.title;
      const copy = document.createElement("p");
      copy.textContent = activity.copy;
      content.append(title, copy);
      item.append(icon, content);
      return item;
    }));

    const fishList = document.querySelector("#fish-progress-list");
    fishList.replaceChildren(...progress.byFish.map((fish) => {
      const item = document.createElement("article");
      item.className = "fish-progress-item";
      const copy = document.createElement("div");
      copy.className = "fish-progress-copy";
      const name = document.createElement("strong");
      name.textContent = fish.canonical_name;
      const count = document.createElement("span");
      const remaining = Math.max(0, fish.total - fish.completed);
      count.textContent = `${fish.completed} / ${fish.total} 張 · ${Math.round(fish.percent)}%`;
      copy.append(name, count);
      const track = document.createElement("div");
      track.className = "progress-track";
      const bar = document.createElement("div");
      bar.className = "progress-bar";
      bar.style.width = `${fish.percent}%`;
      track.append(bar);
      item.append(copy, track);
      if (remaining > 0 && remaining <= 5) {
        const reminder = document.createElement("p");
        reminder.className = "near-complete-reminder";
        reminder.textContent = `再完成 ${remaining} 張，就完成這個魚種！`;
        item.append(reminder);
      }
      return item;
    }));

    const unlockedCount = badges.filter((badge) => badge.unlocked).length;
    document.querySelector("#badge-summary").textContent = `已解鎖 ${unlockedCount} / ${badges.length} 枚勳章`;
    const badgeGrid = document.querySelector("#badge-grid");
    badgeGrid.replaceChildren(...badges.map((badge) => {
      const card = document.createElement("article");
      card.className = `badge-card${badge.unlocked ? "" : " locked"}`;
      const icon = document.createElement("span");
      icon.className = "badge-icon";
      icon.setAttribute("aria-hidden", "true");
      icon.textContent = badge.unlocked ? badge.icon : "🔒";
      const name = document.createElement("strong");
      name.textContent = badge.name;
      const description = document.createElement("p");
      description.textContent = `${badge.description}${badge.unlocked ? " · 已解鎖" : ""}`;
      card.append(icon, name, description);
      return card;
    }));

    const collectedCount = progress.byFish.filter((fish) => fish.completed > 0).length;
    document.querySelector("#collection-summary").textContent = `已點亮 ${collectedCount} / ${progress.byFish.length} 種魚類`;
    const collectionGrid = document.querySelector("#collection-grid");
    collectionGrid.replaceChildren(...progress.byFish.map((fish) => {
      const unlocked = fish.completed > 0;
      const card = document.createElement("article");
      card.className = `collection-card${unlocked ? "" : " locked"}${discoveredFish.has(fish.fish_id) ? " newly-discovered" : ""}`;
      if (unlocked) {
        const image = document.createElement("img");
        image.src = fish.reference_image;
        image.alt = `${fish.canonical_name}收藏圖鑑`;
        image.loading = "lazy";
        card.append(image);
      }
      const copy = document.createElement("div");
      copy.className = "collection-card-copy";
      const name = document.createElement("strong");
      name.textContent = fish.canonical_name;
      const status = document.createElement("span");
      status.textContent = unlocked ? `已收藏 · 判斷 ${fish.completed} 張` : "完成第一題即可點亮";
      copy.append(name, status);
      card.append(copy);
      if (discoveredFish.has(fish.fish_id)) {
        const badge = document.createElement("span");
        badge.className = "new-discovery-label";
        badge.textContent = "新發現";
        card.append(badge);
      }
      return card;
    }));
    this.showScreen("dashboard-screen");
  }

  renderCompletion(stats) {
    document.querySelector("#complete-images").textContent = stats.images.toLocaleString("zh-TW");
    document.querySelector("#complete-questions").textContent = stats.questions.toLocaleString("zh-TW");
    this.showScreen("completion-screen");
  }

  confirm({ title = "請確認", message, confirmText = "確定", cancelText = "返回檢查" }) {
    const dialog = document.querySelector("#confirm-dialog");
    document.querySelector("#confirm-title").textContent = title;
    document.querySelector("#confirm-message").textContent = message;
    const confirmButton = dialog.querySelector('[value="confirm"]');
    const cancelButton = dialog.querySelector('[value="cancel"]');
    confirmButton.textContent = confirmText;
    cancelButton.textContent = cancelText;
    return new Promise((resolve) => {
      const close = () => { dialog.removeEventListener("close", close); resolve(dialog.returnValue === "confirm"); };
      dialog.addEventListener("close", close);
      dialog.showModal();
    });
  }
}
