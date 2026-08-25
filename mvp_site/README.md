# 魚類影像人工標註 MVP

這是一個以 GitHub Pages 提供前端、Supabase 提供登入與共享資料的魚類影像標註網站。Google 登入是必要條件，所有有效標註都會同步到 Supabase。

## 在本機執行

請在專案根目錄執行：

```bash
# 1. 從現有資料建立靜態網站資料與最佳化參考照片
python3 scripts/prepare_mvp_site.py

# 可調整照片尺寸與 WebP 品質
python3 scripts/prepare_mvp_site.py --max-image-dimension 1600 --webp-quality 80

# 2. 啟動靜態 HTTP 伺服器
python3 -m http.server 8000 --directory mvp_site
```

開啟 <http://localhost:8000>。不要直接以 `file://` 開啟 `index.html`，因為瀏覽器通常會阻擋 JSON 載入。

準備腳本需要 Pillow；目前專案環境已使用它處理照片。若環境尚未安裝，可執行 `python3 -m pip install Pillow`。

## 資料流

- 魚種：`Fish_Map/fish_taxonomy.csv`
- 參考照片與魚種關聯：`Fish_Map/photo_targets.csv`
- 上游候選池中繼資料：`Candidate_Pool/manifest.json`
- 上游候選池：`Candidate_Pool/by_fish/*.json`
- 原始參考照片：`Photos/*`
- 網站索引：`mvp_site/data/index.json`
- 網站精簡候選池：`mvp_site/data/candidates/*.json`
- 去除 EXIF、校正方向、縮放後的 WebP：`mvp_site/assets/reference/*.webp`

腳本不會修改 `Photos/` 或 `Candidate_Pool/`。同一張照片若對應多個魚種，會建立不同且穩定的 `target_id`；最佳化照片只產生一次。缺少照片、 taxonomy、候選池或可用候選圖片的目標會被略過並顯示警告，不會中斷整批準備。

## 標註與匯出

本 MVP 使用具版本號的 localStorage keys：

- `fish_labeler_mvp_v1_profile`
- `fish_labeler_mvp_v1_sessions`
- `fish_labeler_mvp_v1_annotations`
- `fish_labeler_mvp_v1_current_question`

右上角「資料選單」可匯出 UTF-8 CSV（含 BOM，方便 Excel 顯示中文）或 JSON。JSON 包含 profile、sessions、資料集摘要與 annotations。損壞的 app 儲存值會盡量以 `fish_labeler_mvp_v1_corrupt_*` 備份，之後可隨 JSON 匯出。

登入後預設進入「我的進度」Dashboard，再由使用者選擇開始或繼續辨識；未登入者不能提交標註。Dashboard 顯示目前資料集的總完成率、各魚種完成率、每日 10 題挑戰、連續參與天數、下一個里程碑、收藏圖鑑與個人成就勳章。統計只計入相同 `dataset_id`、相同標註者的不重複候選圖片；挑戰、連續天數與勳章均由現有標註即時計算，不另存一份容易不同步的狀態。

排行榜透過 Supabase 的 aggregate RPC 顯示全部與本週前 20 名，只公開暱稱與標註數量，不公開個別填答內容。

「重設本機資料」只會清除以上 `fish_labeler_mvp_v1_*` keys，不會清除其他網站資料；操作前會再次確認。

## Supabase 連線

資料庫 schema 已透過 `supabase/migrations/` 推送到遠端 Supabase。若要在本機載入 Supabase JavaScript SDK，請將 `js/supabase-config.example.js` 複製成 `js/supabase-config.js`，填入 Project URL 與 publishable key。`supabase-config.js` 已列入 `.gitignore`，不可提交；service role key、database password 與 OAuth secret 絕對不能放在前端。

Google 登入後，網站會讀取目前資料集的遠端 annotations，並在送出題目後同步寫入 Supabase；localStorage 只作為登入狀態與暫存，不提供未登入標註模式。

## 設定與架構

在 `js/app.js` 修改：

```js
export const APP_CONFIG = Object.freeze({
  candidatesPerQuestion: 10,
  debug: false,
  appVersion: "mvp-1",
});
```

開啟 `debug` 會顯示 fish、target、candidate、來源 URL 與 dataset ID。

程式刻意分成以下邊界：

- `scripts/prepare_mvp_site.py`：上游原始資料 → 靜態資料集
- `js/data.js`：按題目延遲讀取靜態 JSON
- `js/game.js`：抽題、排除已標註候選、序列化 judgments
- `js/ui.js`：畫面與互動
- `js/storage.js`：`AnnotationStore` 介面與 `LocalStorageAnnotationStore`
- `js/app.js`：組裝與事件流程

網站使用相對路徑與標準靜態資產，可部署到 GitHub Pages。`.github/workflows/deploy-pages.yml` 會在部署時以 GitHub Repository Variables 注入 `mvp_site/js/supabase-config.js`，因此本機設定檔不需要提交。

## GitHub Pages 部署

1. 將專案放在使用者網站 repository `amyhsiao/amyhsiao.github.io`，在其 **Settings → Pages** 將 Source 設為 **GitHub Actions**。workflow 會把 `mvp_site/` 部署到 `TWfisher/` 子路徑。
2. 在 **Settings → Secrets and variables → Actions → Variables** 新增：
   - `SUPABASE_URL`：Supabase Project URL
   - `SUPABASE_PUBLISHABLE_KEY`：Supabase publishable／anon key（可公開，不可使用 service role key）
3. 先將排行榜與 Storage migrations 推送到 Supabase：

```bash
npx supabase login
SUPABASE_TELEMETRY_DISABLED=1 npx supabase db push --linked
```

4. 部署完成後，將以下網址加入 Supabase **Authentication → URL Configuration** 的 Site URL 與 Redirect URLs：

```text
https://amyhsiao.github.io/TWfisher/
```

候選卡片會優先載入縮圖，來源連結才會開啟來源頁或原圖。常用候選圖若要完全自有化，可使用 `scripts/mirror_candidate_images.py` 鏡像到 `candidate-images` Storage bucket；外部圖片仍可作為 fallback。

## 開發驗證

輕量測試不需要前端測試框架：

```bash
python3 -m pytest -q
node --test tests/js/test_mvp.mjs
```

`scripts/smoke_test_mvp.py` 是以 Chrome DevTools Protocol 驗證實際瀏覽器流程的無相依性輔助工具；一般使用者不需要執行它。
