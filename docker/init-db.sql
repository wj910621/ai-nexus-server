-- 数据库初始化脚本
-- 启用必要的扩展
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pg_trgm";

-- 注意: pgvector 扩展需要单独安装，如需使用请运行:
-- CREATE EXTENSION IF NOT EXISTS vector;

-- 注释
\echo '数据库 comic_studio 初始化完成'
