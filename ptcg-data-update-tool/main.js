const pokemon = require("pokemontcgsdk");
const DBImporter = require("./dbImporter.js");
const PTCGCardStore = require("./ptcgCardStore");
const axios = require("axios");
const { Client } = require("pg");
const fs = require("fs");
const path = require("path");
const fsp = fs.promises;

var client = new Client({
  host: "localhost",
  port: 5432,
  user: "postgres",
  password: "postgres",
  database: "ptcg",
});

async function connect() {
  await client.connect();
  console.log("✅ Connected to Postgres");
}

async function disconnect() {
  await client.end();
  console.log("🔌 Connection closed");
}

connect();

pokemon.configure({ apiKey: "50511606-bf4b-4c8b-9e9b-085116d09f84" });
console.log("finish configure");

const FETCH_CONCURRENCY =
  parseInt(process.env.CARD_FETCH_CONCURRENCY, 10) || 10;
const CARD_LANGUAGE = process.env.CARD_FILE_LANGUAGE || "en";
const cardsBaseDir = path.join(__dirname, "cards");
const setCardCache = new Map();

let retryData = [];

async function cardExists(card_id) {
  try {
    const res = await client.query(
      "SELECT 1 FROM ptcg_cards WHERE id = $1 LIMIT 1",
      [card_id]
    );
    return res.rowCount > 0;
  } catch (err) {
    console.error("⚠️ 检查数据库中是否已存在卡牌时出错：", err.message);
    return false;
  }
}

async function loadLocalSetCards(setId) {
  if (setCardCache.has(setId)) {
    return setCardCache.get(setId);
  }

  const filePath = path.join(cardsBaseDir, CARD_LANGUAGE, `${setId}.json`);
  try {
    const file = await fsp.readFile(filePath, "utf8");
    const data = JSON.parse(file);
    if (!Array.isArray(data)) {
      console.warn(`⚠️ 本地卡牌文件格式异常：${filePath}`);
      setCardCache.set(setId, null);
      return null;
    }
    setCardCache.set(setId, data);
    return data;
  } catch (err) {
    console.warn(`⚠️ 找不到本地卡牌文件 ${filePath}：${err.message}`);
    setCardCache.set(setId, null);
    return null;
  }
}

async function findCardLocally(cardId, setId) {
  const cards = await loadLocalSetCards(setId);
  if (!cards) return null;
  return cards.find((card) => card.id === cardId) || null;
}

function padNumber(num, width) {
  const str = num.toString();
  return str.padStart(width, "0");
}

function getCardId(setId, index) {
  if (setId == "swsh12pt5gg") {
    return `swsh12pt5gg-GG${padNumber(index, 2)}`;
  } else if (setId == "xyp") {
    return `xyp-XY${padNumber(index, 2)}`;
  } else if (setId == "swshp") {
    return `swshp-SWSH${padNumber(index, 3)}`;
  } else if (setId == "swsh45sv") {
    return `swsh45sv-SV${padNumber(index, 3)}`;
  } else if (setId == "swsh12tg") {
    return `swsh12tg-TG${padNumber(index, 2)}`;
  } else if (setId == "swsh11tg") {
    return `swsh11tg-TG${padNumber(index, 2)}`;
  } else if (setId == "swsh10tg") {
    return `swsh10tg-TG${padNumber(index, 2)}`;
  } else if (setId == "swsh9tg") {
    return `swsh9tg-TG${padNumber(index, 2)}`;
  } else if (setId == "smp") {
    return `smp-SM${padNumber(index, 2)}`;
  } else if (setId == "sma") {
    return `sma-SV${index}`;
  } else if (setId == "hsp") {
    return `hsp-HGSS${padNumber(index, 2)}`;
  } else if (setId == "dpp") {
    return `dpp-DP${padNumber(index, 2)}`;
  }  else if (setId == "bwp") {
    return `bwp-BW${padNumber(index, 2)}`;
  }

  return `${setId}-${index}`;
}

async function getData(store, set_id, index, total) {
  try {
    let card_id = getCardId(set_id, index);
    //let card_id = set_id + "-" + index;
    if (await cardExists(card_id)) {
      console.log("⏩ 数据库已存在，跳过请求：", card_id);
      return;
    }
    const localCard = await findCardLocally(card_id, set_id);
    if (localCard) {
      await store.importFromJSON(localCard);
      console.log("📦 使用本地缓存写入数据库：", card_id);
      return;
    }
    retryData.push({
      set_id: set_id,
      index: index,
    });

    /*
    console.log("开始请求数据：", card_id);
    const res = await axios.get(
      "https://api.pokemontcg.io/v2/cards/" + set_id + "-" + index,
      {
        headers: {
          "X-Api-Key": "50511606-bf4b-4c8b-9e9b-085116d09f84",
        },
      }
    );
    //let card = await pokemon.card.find(card_id);
    let card = res.data.data;
    await store.importFromJSON(card);
    console.log(
      "✅ 已写入数据库：" + card.name + ", 剩余任务：" + index + " / " + total
    );*/
  } catch (err) {
    console.error(
      "❌ 请求失败：" + err.message + ", 剩余任务：" + index + " / " + total
    );
    retryData.push({
      set_id: set_id,
      index: index,
    });
  }
}

async function runWithConcurrency(items, limit, iterator) {
  if (!items.length) return;
  const workerCount = Math.min(limit || 1, items.length);
  let cursor = 0;

  async function worker() {
    while (true) {
      const currentIndex = cursor;
      if (currentIndex >= items.length) {
        break;
      }
      cursor++;
      await iterator(items[currentIndex]);
    }
  }

  await Promise.all(new Array(workerCount).fill(null).map(() => worker()));
}

const importer = new DBImporter(client);

const store = new PTCGCardStore(client);

(async () => {
  try {
    await importer.createTable();
    await importer.importFromJSON("./setdata.json");

    await store.createTable();

    const rows = await importer.fetchAllSets();

    // ✅ 遍历每一行
    for (let i = rows.length - 1; i >= 0; i--) {
      const row = rows[i];
      console.log(`${row.id} | ${row.name} | ${row.series} | ${row.total}`);
      let total = parseInt(row.total);
      const indexes = Array.from({ length: total }, (_, idx) => idx + 1);
      console.log(
        `🚀 并发获取 ${row.id} 的卡牌数据，最大并发：${FETCH_CONCURRENCY}`
      );
      await runWithConcurrency(indexes, FETCH_CONCURRENCY, (cardIndex) =>
        getData(store, row.id, cardIndex, total)
      );
    }
  } catch (e) {
    console.error(e);
  } finally {
    await disconnect();
    //const jsonStr = JSON.stringify(retryData, null, 2);
    //fs.writeFileSync("retry.json", jsonStr, "utf8");
  }
})();
