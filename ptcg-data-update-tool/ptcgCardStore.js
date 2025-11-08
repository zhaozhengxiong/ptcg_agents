// ptcgCardStore.js
const fs = require('fs');
const { Client } = require('pg');

class PTCGCardStore {
  constructor(client) {
    this.client = client;
  }

  /**
   * 创建表：根据当前 card JSON 的结构设计
   * 如果已存在则跳过（IF NOT EXISTS）
   */
  async createTable() {
    const sql = `
      CREATE TABLE IF NOT EXISTS ptcg_cards (
        id                      TEXT PRIMARY KEY,
        name                    TEXT NOT NULL,
        supertype               TEXT,
        subtypes                TEXT[],
        hp                      INTEGER,
        types                   TEXT[],
        evolves_from            TEXT,
        "number"                TEXT,
        artist                  TEXT,
        rarity                  TEXT,
        flavor_text             TEXT,
        rules                   TEXT[],
        regulation_mark         TEXT,
        national_pokedex_numbers INTEGER[],
        -- 套牌信息（从 card.set 里拆）
        set_id                  TEXT,
        set_name                TEXT,
        set_series              TEXT,
        set_ptcgo_code          TEXT,
        set_release_date        DATE,
        set_printed_total       INTEGER,
        set_total               INTEGER,
        set_updated_at          TEXT,
        set_legalities          JSONB,
        set_symbol_url          TEXT,
        set_logo_url            TEXT,
        -- 卡本身图片
        image_small             TEXT,
        image_large             TEXT,
        -- 各类规则 / 价格信息等，用 JSONB 存储
        legalities              JSONB,
        abilities               JSONB,
        attacks                 JSONB,
        weaknesses              JSONB,
        retreat_cost            TEXT[],
        converted_retreat_cost  INTEGER,
        tcgplayer_url           TEXT,
        tcgplayer_prices        JSONB,
        cardmarket_url          TEXT,
        cardmarket_prices       JSONB,
        -- 原始数据留一份，方便以后扩展（可选）
        raw                     JSONB
      );
    `;
    await this.client.query(sql);
    console.log('🧱 Table ptcg_cards ready');
  }

  /**
   * 将 JSON 写入表中（数据库去重）
   * 支持三种格式：
   *  - { data: [ {...}, {...} ] }
   *  - [ {...}, {...} ]
   *  - 单条 { ... }
   *
   * 去重策略：
   *  - 以 id 为 PRIMARY KEY
   *  - ON CONFLICT (id) DO UPDATE：已存在则更新为最新数据
   *    若你想“已有就跳过”，把下面 SQL 里的 DO UPDATE 改成 DO NOTHING
   */
  async importFromJSON(data) {
    const parsed = data;

    let cards;
    if (Array.isArray(parsed)) {
      cards = parsed;
    } else if (Array.isArray(parsed.data)) {
      cards = parsed.data;
    } else if (parsed && parsed.id && parsed.name) {
      cards = [parsed];
    } else {
      throw new Error('无法识别的 JSON 结构：需要是 data 数组、数组或单个卡片对象');
    }

    const sql = `
      INSERT INTO ptcg_cards (
        id,
        name,
        supertype,
        subtypes,
        hp,
        types,
        evolves_from,
        "number",
        artist,
        rarity,
        flavor_text,
        rules,
        regulation_mark,
        national_pokedex_numbers,
        set_id,
        set_name,
        set_series,
        set_ptcgo_code,
        set_release_date,
        set_printed_total,
        set_total,
        set_updated_at,
        set_legalities,
        set_symbol_url,
        set_logo_url,
        image_small,
        image_large,
        legalities,
        abilities,
        attacks,
        weaknesses,
        retreat_cost,
        converted_retreat_cost,
        tcgplayer_url,
        tcgplayer_prices,
        cardmarket_url,
        cardmarket_prices,
        raw
      )
      VALUES (
        $1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,
        $12,$13,$14,
        $15,$16,$17,$18,$19,$20,$21,$22,$23,
        $24,$25,
        $26,$27,$28,$29,
        $30,$31,$32,$33,$34,$35,$36,$37,$38
      )
      ON CONFLICT (id) DO UPDATE SET
        name                   = EXCLUDED.name,
        supertype              = EXCLUDED.supertype,
        subtypes               = EXCLUDED.subtypes,
        hp                     = EXCLUDED.hp,
        types                  = EXCLUDED.types,
        evolves_from           = EXCLUDED.evolves_from,
        "number"               = EXCLUDED."number",
        artist                 = EXCLUDED.artist,
        rarity                 = EXCLUDED.rarity,
        flavor_text            = EXCLUDED.flavor_text,
        rules                  = EXCLUDED.rules,
        regulation_mark        = EXCLUDED.regulation_mark,
        national_pokedex_numbers = EXCLUDED.national_pokedex_numbers,
        set_id                 = EXCLUDED.set_id,
        set_name               = EXCLUDED.set_name,
        set_series             = EXCLUDED.set_series,
        set_ptcgo_code         = EXCLUDED.set_ptcgo_code,
        set_release_date       = EXCLUDED.set_release_date,
        set_printed_total      = EXCLUDED.set_printed_total,
        set_total              = EXCLUDED.set_total,
        set_updated_at         = EXCLUDED.set_updated_at,
        set_legalities         = EXCLUDED.set_legalities,
        set_symbol_url         = EXCLUDED.set_symbol_url,
        set_logo_url           = EXCLUDED.set_logo_url,
        image_small            = EXCLUDED.image_small,
        image_large            = EXCLUDED.image_large,
        legalities             = EXCLUDED.legalities,
        abilities              = EXCLUDED.abilities,
        attacks                = EXCLUDED.attacks,
        weaknesses             = EXCLUDED.weaknesses,
        retreat_cost           = EXCLUDED.retreat_cost,
        converted_retreat_cost = EXCLUDED.converted_retreat_cost,
        tcgplayer_url          = EXCLUDED.tcgplayer_url,
        tcgplayer_prices       = EXCLUDED.tcgplayer_prices,
        cardmarket_url         = EXCLUDED.cardmarket_url,
        cardmarket_prices      = EXCLUDED.cardmarket_prices,
        raw                    = EXCLUDED.raw;
      -- 如果想改成“已存在就不更新”，把上面整段 DO UPDATE 替换为：
      -- ON CONFLICT (id) DO NOTHING;
    `;

    await this.client.query('BEGIN');
    try {
      for (const c of cards) {
        const set = c.set || {};
        const setImages = (set && set.images) || {};
        const images = c.images || {};
        const tcgplayer = c.tcgplayer || {};
        const cardmarket = c.cardmarket || {};

        const hp = c.hp ? parseInt(c.hp, 10) || null : null;

        const rules = Array.isArray(c.rules) && c.rules.length ? c.rules : null;
        const regulationMark = c.regulationMark || null;
        let nationalPokedexNumbers = null;
        if (Array.isArray(c.nationalPokedexNumbers) && c.nationalPokedexNumbers.length) {
          const parsed = c.nationalPokedexNumbers
            .map((num) => (typeof num === 'number' ? num : parseInt(num, 10)))
            .filter((num) => Number.isFinite(num));
          nationalPokedexNumbers = parsed.length ? parsed : null;
        }

        const setPrintedTotal =
          set.printedTotal !== undefined && set.printedTotal !== null
            ? parseInt(set.printedTotal, 10) || null
            : null;
        const setTotal =
          set.total !== undefined && set.total !== null
            ? parseInt(set.total, 10) || null
            : null;

        await this.client.query(sql, [
          c.id,
          c.name || null,
          c.supertype || null,
          c.subtypes && c.subtypes.length ? c.subtypes : null,
          hp,
          c.types && c.types.length ? c.types : null,
          c.evolvesFrom || null,
          c.number || null,
          c.artist || null,
          c.rarity || null,
          c.flavorText || null,
          rules,
          regulationMark,
          nationalPokedexNumbers,
          set.id || null,
          set.name || null,
          set.series || null,
          set.ptcgoCode || null,
          set.releaseDate || null,
          setPrintedTotal,
          setTotal,
          set.updatedAt || null,
          set.legalities ? JSON.stringify(set.legalities) : null,
          setImages.symbol || null,
          setImages.logo || null,
          images.small || null,
          images.large || null,
          c.legalities ? JSON.stringify(c.legalities) : null,
          c.abilities ? JSON.stringify(c.abilities) : null,
          c.attacks ? JSON.stringify(c.attacks) : null,
          c.weaknesses ? JSON.stringify(c.weaknesses) : null,
          c.retreatCost && c.retreatCost.length ? c.retreatCost : null,
          c.convertedRetreatCost ?? null,
          tcgplayer.url || null,
          tcgplayer.prices ? JSON.stringify(tcgplayer.prices) : null,
          cardmarket.url || null,
          cardmarket.prices ? JSON.stringify(cardmarket.prices) : null,
          JSON.stringify(c),
        ]);
      }

      await this.client.query('COMMIT');
      console.log(`✅ 导入完成（含数据库去重保护），处理 ${cards.length} 条记录`);
    } catch (err) {
      await this.client.query('ROLLBACK');
      console.error('❌ 导入失败：', err);
      throw err;
    }
  }
}

module.exports = PTCGCardStore;
