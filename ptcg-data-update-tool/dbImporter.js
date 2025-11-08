// dbImporter.js
const fs = require('fs');
const { Client } = require('pg');

class DBImporter {
  constructor(client) {
    this.client = client;
  }

  async fetchAllSets() {
    const res = await this.client.query('SELECT * FROM ptcg_sets ORDER BY release_date ASC;');
    console.log(`📦 共获取 ${res.rows.length} 条记录`);
    return res.rows;
  }

  async createTable() {
    const createTableSQL = `
      CREATE TABLE IF NOT EXISTS ptcg_sets (
        id              TEXT PRIMARY KEY,
        name            TEXT NOT NULL,
        series          TEXT,
        printed_total   INTEGER,
        total           INTEGER,
        legal_unlimited TEXT,
        legal_expanded  TEXT,
        ptcgo_code      TEXT,
        release_date    DATE,
        updated_at      TIMESTAMP,
        symbol_url      TEXT,
        logo_url        TEXT
      );
    `;
    await this.client.query(createTableSQL);
    console.log('🧱 Table ready');
  }

  /**
   * 从 JSON 导入，依靠数据库 PRIMARY KEY 去重。
   * 如果 id 已存在，则更新为最新记录。
   */
  async importFromJSON(filePath) {
    const raw = fs.readFileSync(filePath, 'utf8');
    const json = JSON.parse(raw);
    const sets = json.data;
    if (!Array.isArray(sets)) {
      throw new Error('JSON 格式错误：缺少 data 数组');
    }

    const insertSQL = `
      INSERT INTO ptcg_sets (
        id,
        name,
        series,
        printed_total,
        total,
        legal_unlimited,
        legal_expanded,
        ptcgo_code,
        release_date,
        updated_at,
        symbol_url,
        logo_url
      )
      VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12)
      ON CONFLICT (id) DO UPDATE SET
        name            = EXCLUDED.name,
        series          = EXCLUDED.series,
        printed_total   = EXCLUDED.printed_total,
        total           = EXCLUDED.total,
        legal_unlimited = EXCLUDED.legal_unlimited,
        legal_expanded  = EXCLUDED.legal_expanded,
        ptcgo_code      = EXCLUDED.ptcgo_code,
        release_date    = EXCLUDED.release_date,
        updated_at      = EXCLUDED.updated_at,
        symbol_url      = EXCLUDED.symbol_url,
        logo_url        = EXCLUDED.logo_url;
      -- 若只想跳过已有记录，请改为：ON CONFLICT (id) DO NOTHING;
    `;

    await this.client.query('BEGIN');
    try {
      for (const s of sets) {
        const legal = s.legalities || {};
        const images = s.images || {};

        await this.client.query(insertSQL, [
          s.id,
          s.name,
          s.series || null,
          s.printedTotal ?? null,
          s.total ?? null,
          legal.unlimited || null,
          legal.expanded || null,
          s.ptcgoCode || null,
          s.releaseDate || null,
          s.updatedAt || null,
          images.symbol || null,
          images.logo || null,
        ]);
      }
      await this.client.query('COMMIT');
      console.log(`✅ 成功写入（含数据库去重）${sets.length} 条数据`);
    } catch (err) {
      await this.client.query('ROLLBACK');
      console.error('❌ 导入出错：', err);
      throw err;
    }
  }
}

module.exports = DBImporter;


