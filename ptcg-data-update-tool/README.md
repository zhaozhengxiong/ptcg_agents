# PTCG数据库工具

## 备份 ptcg
npm run backup:ptcg

## 用备份还原 ptcg（会删库并重建 + 配置 postgres/postgres 用户）
npm run restore:ptcg

### 搭建新环境时，建议使用`npm run restore:ptcg`配置好数据库，或手动使用`./backup/ptcg_backup.sql`文件还原
