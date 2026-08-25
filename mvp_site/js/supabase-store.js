function uuidFromClientId(value) {
  if (!value) return null;
  const match = String(value).match(/(?:annotation_|session_|question_)?([0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12})$/i);
  return match ? match[1] : null;
}

function clientId(prefix, value) {
  return value ? `${prefix}${value}` : null;
}

export class SupabaseAnnotationSync {
  constructor(client, userId) {
    this.client = client;
    this.userId = userId;
    this.profile = null;
  }

  async prepare(dataset) {
    const { error: datasetError } = await this.client.from("datasets").insert({
      dataset_id: dataset.dataset_id,
      generated_at: dataset.generated_at,
      task_count: dataset.task_count,
      candidate_count: dataset.candidate_count,
      metadata: { fish_pool_count: dataset.fish_pool_count },
    });
    if (datasetError && datasetError.code !== "23505") throw datasetError;
    const { data, error } = await this.client.from("annotations")
      .select("*")
      .eq("user_id", this.userId)
      .eq("dataset_id", dataset.dataset_id);
    if (error) throw error;
    return (data || []).map((row) => ({
      annotation_id: clientId("annotation_", row.id),
      session_id: clientId("session_", row.session_id),
      annotator_id: row.user_id,
      display_name: this.profile?.display_name || "",
      target_id: row.target_id,
      fish_id: row.fish_id,
      canonical_name: row.canonical_name,
      reference_filename: row.reference_filename || "",
      candidate_id: row.candidate_id,
      candidate_image_url: row.candidate_image_url || "",
      candidate_source_page_url: row.candidate_source_page_url || "",
      judgment: row.judgment,
      position: row.position,
      question_batch_id: clientId("question_", row.question_batch_id),
      dataset_id: row.dataset_id,
      created_at: row.created_at,
      app_version: "supabase",
    }));
  }

  async syncIdentity(profile, session, dataset) {
    this.profile = profile;
    const { error: profileError } = await this.client.from("profiles").upsert({
      id: this.userId,
      display_name: profile.display_name,
    });
    if (profileError) throw profileError;
    const sessionId = uuidFromClientId(session?.session_id);
    if (sessionId) {
      const { error: sessionError } = await this.client.from("labeling_sessions").insert({
        id: sessionId,
        user_id: this.userId,
        dataset_id: dataset.dataset_id,
        started_at: session.started_at,
      });
      if (sessionError && sessionError.code !== "23505") throw sessionError;
    }
  }

  async saveAnnotationBatch(records) {
    if (!records.length) return;
    const datasetId = records[0].dataset_id;
    const { data: existing, error: existingError } = await this.client.from("annotations")
      .select("fish_id,candidate_id")
      .eq("user_id", this.userId)
      .eq("dataset_id", datasetId);
    if (existingError) throw existingError;
    const existingKeys = new Set((existing || []).map((row) => `${row.fish_id}:${row.candidate_id}`));
    const rows = records.filter((record) => !existingKeys.has(`${record.fish_id}:${record.candidate_id}`)).map((record) => ({
      id: uuidFromClientId(record.annotation_id),
      user_id: this.userId,
      session_id: uuidFromClientId(record.session_id),
      dataset_id: record.dataset_id,
      target_id: record.target_id,
      fish_id: record.fish_id,
      canonical_name: record.canonical_name,
      reference_filename: record.reference_filename || null,
      candidate_id: record.candidate_id,
      candidate_image_url: record.candidate_image_url || null,
      candidate_source_page_url: record.candidate_source_page_url || null,
      judgment: record.judgment,
      position: record.position,
      question_batch_id: uuidFromClientId(record.question_batch_id),
      created_at: record.created_at,
    }));
    if (!rows.length) return;
    const { error } = await this.client.from("annotations").insert(rows);
    if (error) throw error;
  }

  async getLeaderboard(datasetId, period = "all") {
    const { data, error } = await this.client.rpc("get_annotation_leaderboard", {
      p_dataset_id: datasetId,
      p_period: period,
    });
    if (error) throw error;
    return data || [];
  }
}
