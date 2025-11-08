#!/usr/bin/env node

/**
 * backup.js
 *
 * 用法（配合 package.json）：
 *   npm run backup:ptcg
 *   npm run restore:ptcg
 *
 * 环境要求：
 *   1. 已安装并可在 PATH 中找到：pg_dump, psql, dropdb, createdb
 *   2. 根目录存在 .env 或已设置环境变量：
 *        PGHOST, PGPORT, PGUSER, PGPASSWORD
 *      脚本启动时会自动加载 .env（通过 dotenv）。
 *
 * 功能：
 *   backup  ：备份 ptcg 到指定文件
 *   restore ：使用备份文件还原 ptcg，并确保创建/配置 postgres 用户：
 *             用户名 postgres，密码 postgres，且有操作 ptcg 的权限
 */

require("dotenv").config(); // 自动加载 .env

const { spawnSync } = require("child_process");
const fs = require("fs");
const path = require("path");

const DB_NAME = "ptcg";

function parseArgs() {
  const args = process.argv.slice(2);
  if (args.length === 0) {
    printHelpAndExit("缺少指令（backup 或 restore）");
  }

  const command = args[0];
  const options = {};

  for (let i = 1; i < args.length; i++) {
    if (args[i] === "--file" && args[i + 1]) {
      options.file = args[i + 1];
      i++;
    }
  }

  if (!options.file) {
    printHelpAndExit("必须通过 --file 指定备份文件路径");
  }

  return { command, options };
}

function printHelpAndExit(msg) {
  if (msg) console.error("[错误]", msg);
  console.log(`
用法：
  node backup.js backup --file ./backup/ptcg_backup.sql
  node backup.js restore --file ./backup/ptcg_backup.sql

说明：
  - 数据库连接信息从环境变量读取，可通过 .env 提供：
      PGHOST, PGPORT, PGUSER, PGPASSWORD
  - 建议 PGUSER 为有权限 dropdb/createdb/创建角色 的管理员账号。
`);
  process.exit(1);
}

function run(cmd, args, options = {}) {
  console.log(`\n[执行] ${cmd} ${args.join(" ")}`);
  const result = spawnSync(cmd, args, {
    stdio: "inherit",
    env: process.env,
    shell: process.platform === "win32",
    ...options,
  });

  if (result.error) {
    console.error(`[错误] 无法执行 ${cmd}:`, result.error.message);
    process.exit(1);
  }

  if (result.status !== 0) {
    console.error(`[错误] 命令退出码：${result.status}`);
    process.exit(result.status);
  }
}

function ensureDirExists(filePath) {
  const dir = path.dirname(filePath);
  if (!fs.existsSync(dir)) {
    fs.mkdirSync(dir, { recursive: true });
  }
}

/**
 * 备份 ptcg 数据库为 SQL 文本
 */
function backup({ file }) {
  ensureDirExists(file);

  const args = [
    "-d",
    DB_NAME,
    "-F",
    "p",
    "-f",
    file,
  ];

  run("pg_dump", args);
  console.log(`\n[完成] 数据库 "${DB_NAME}" 已备份到：${file}`);
}

/**
 * 确保存在 postgres 用户（用户名=postgres，密码=postgres），并赋予操作 ptcg 的权限
 */
function ensurePostgresUserForPtcg() {
  console.log("\n[步骤] 确保存在用户 postgres（密码 postgres），并配置 ptcg 权限");

  const createRoleSql = `
DO $$
BEGIN
  IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'postgres') THEN
    CREATE ROLE postgres LOGIN PASSWORD 'postgres';
  ELSE
    ALTER ROLE postgres LOGIN PASSWORD 'postgres';
  END IF;
END$$;
`;

  // 在 postgres 系统库上执行角色语句
  run("psql", ["-d", "postgres", "-v", "ON_ERROR_STOP=1", "-c", createRoleSql]);

  const grantDbSql = `
GRANT ALL PRIVILEGES ON DATABASE "${DB_NAME}" TO postgres;
ALTER DATABASE "${DB_NAME}" OWNER TO postgres;
`;

  run("psql", ["-d", "postgres", "-v", "ON_ERROR_STOP=1", "-c", grantDbSql]);

  const grantObjectsSql = `
GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO postgres;
GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public TO postgres;
GRANT ALL PRIVILEGES ON ALL FUNCTIONS IN SCHEMA public TO postgres;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON TABLES TO postgres;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON SEQUENCES TO postgres;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON FUNCTIONS TO postgres;
`;

  run("psql", ["-d", DB_NAME, "-v", "ON_ERROR_STOP=1", "-c", grantObjectsSql]);

  console.log(`[完成] 用户 "postgres" 已可操作数据库 "${DB_NAME}"。`);
}

/**
 * 使用备份文件还原 ptcg 数据库
 */
function restore({ file }) {
  if (!fs.existsSync(file)) {
    console.error(`[错误] 找不到备份文件：${file}`);
    process.exit(1);
  }

  console.log("[警告] 即将使用备份文件还原数据库，会删除并重建同名数据库：", DB_NAME);

  run("dropdb", ["--if-exists", DB_NAME]);
  run("createdb", [DB_NAME]);
  run("psql", ["-d", DB_NAME, "-f", file]);

  ensurePostgresUserForPtcg();

  console.log(`\n[完成] 数据库 "${DB_NAME}" 已从备份文件还原并配置 postgres 用户：${file}`);
}

// === main ===
const { command, options } = parseArgs();

if (command === "backup") {
  backup(options);
} else if (command === "restore") {
  restore(options);
} else {
  printHelpAndExit(`未知指令：${command}（只能是 backup 或 restore）`);
}
