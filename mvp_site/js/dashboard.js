export const BADGES = Object.freeze([
  { id: "first_dive", icon: "🐠", name: "初次下潛", description: "完成第一題", unit: "題", value: (progress) => progress.questions, target: () => 1 },
  { id: "sharp_eye", icon: "🔎", name: "觀察之眼", description: "判斷 50 張圖片", unit: "張圖片", value: (progress) => progress.completed, target: () => 50 },
  { id: "species_scout", icon: "🧭", name: "魚種探索者", description: "協助 3 種不同魚類", unit: "種魚", value: (progress) => progress.byFish.filter((fish) => fish.completed > 0).length, target: () => 3 },
  { id: "century", icon: "💯", name: "百張達人", description: "判斷 100 張圖片", unit: "張圖片", value: (progress) => progress.completed, target: () => 100 },
  { id: "hundred_eye", icon: "👁️", name: "百圖慧眼", description: "判斷 250 張圖片", unit: "張圖片", value: (progress) => progress.completed, target: () => 250 },
  { id: "daily_rhythm", icon: "☀️", name: "每日探勘員", description: "完成 10 題，達成一次每日挑戰", unit: "題", value: (progress) => progress.questions, target: () => 10 },
  { id: "species_cartographer", icon: "🗺️", name: "魚種製圖師", description: "探索 10 種不同魚類", unit: "種魚", value: (progress) => progress.byFish.filter((fish) => fish.completed > 0).length, target: () => 10 },
  { id: "species_guardian", icon: "🪸", name: "珊瑚海守護者", description: "探索 25 種不同魚類", unit: "種魚", value: (progress) => progress.byFish.filter((fish) => fish.completed > 0).length, target: () => 25 },
  { id: "five_hundred", icon: "🌊", name: "深海調查員", description: "判斷 500 張圖片", unit: "張圖片", value: (progress) => progress.completed, target: () => 500 },
  { id: "thousand", icon: "🐋", name: "海洋大師", description: "判斷 1,000 張圖片", unit: "張圖片", value: (progress) => progress.completed, target: () => 1000 },
  { id: "full_species", icon: "🧬", name: "百魚圖鑑家", description: "探索 100 種不同魚類", unit: "種魚", value: (progress) => progress.byFish.filter((fish) => fish.completed > 0).length, target: () => 100 },
  { id: "full_catalog", icon: "🏆", name: "圖鑑守護者", description: "完成目前整份資料集", unit: "張圖片", value: (progress) => progress.completed, target: (progress) => progress.total },
]);

export function getBadges(progress) {
  return BADGES.map((badge) => {
    const current = badge.value(progress);
    const target = badge.target(progress);
    return { ...badge, current, target, unlocked: target > 0 && current >= target };
  });
}

export function getNextMilestone(progress) {
  const next = getBadges(progress).find((badge) => !badge.unlocked);
  if (!next) return null;
  return {
    ...next,
    remaining: Math.max(0, next.target - next.current),
    percent: next.target ? Math.min(100, next.current / next.target * 100) : 0,
  };
}
