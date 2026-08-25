export const DAILY_CHALLENGE_TARGET = 10;

// 可在辦理抽獎、限時挑戰或活動公告時加入項目，不需要改 Dashboard 版面。
// 例：{ icon: "🎁", title: "八月標註抽獎", copy: "完成今日挑戰即可參加。" }
export const ACTIVITY_NOTICES = Object.freeze([]);

export function localDateKey(value) {
  const date = value instanceof Date ? value : new Date(value);
  if (Number.isNaN(date.getTime())) return null;
  const year = date.getFullYear();
  const month = String(date.getMonth() + 1).padStart(2, "0");
  const day = String(date.getDate()).padStart(2, "0");
  return `${year}-${month}-${day}`;
}

export function getWeeklyStats(annotations, now = new Date(), target = 30) {
  const start = new Date(now.getFullYear(), now.getMonth(), now.getDate());
  const day = start.getDay() || 7;
  start.setDate(start.getDate() - day + 1);
  const questionIds = new Set();
  for (const item of annotations) {
    const date = new Date(item.created_at);
    if (!Number.isNaN(date.getTime()) && date >= start && item.question_batch_id) questionIds.add(item.question_batch_id);
  }
  const completed = questionIds.size;
  return { completed, target, percent: Math.min(100, completed / target * 100), complete: completed >= target };
}

function addLocalDays(date, days) {
  const result = new Date(date.getFullYear(), date.getMonth(), date.getDate());
  result.setDate(result.getDate() + days);
  return result;
}

export function getEngagementStats(annotations, now = new Date()) {
  const questionDates = new Map();
  for (const item of annotations) {
    const dateKey = localDateKey(item.created_at);
    if (dateKey && item.question_batch_id && !questionDates.has(item.question_batch_id)) {
      questionDates.set(item.question_batch_id, dateKey);
    }
  }
  const activeDates = new Set(questionDates.values());
  const todayKey = localDateKey(now);
  const todayQuestions = [...questionDates.values()].filter((dateKey) => dateKey === todayKey).length;
  const yesterdayKey = localDateKey(addLocalDays(now, -1));
  let cursor = activeDates.has(todayKey) ? new Date(now) : activeDates.has(yesterdayKey) ? addLocalDays(now, -1) : null;
  let streak = 0;
  while (cursor && activeDates.has(localDateKey(cursor))) {
    streak += 1;
    cursor = addLocalDays(cursor, -1);
  }
  return {
    todayQuestions,
    dailyTarget: DAILY_CHALLENGE_TARGET,
    dailyPercent: Math.min(100, todayQuestions / DAILY_CHALLENGE_TARGET * 100),
    dailyComplete: todayQuestions >= DAILY_CHALLENGE_TARGET,
    streak,
    activeDays: activeDates.size,
  };
}
