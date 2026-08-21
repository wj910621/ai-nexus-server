# React Router RSC advisory - 已解决（RESOLVED）

- Advisory: `GHSA-qwww-vcr4-c8h2`（RSC 模式 CSRF）
- 影响依赖: React Router 7.12.0 - 7.18.1
- **原例外截止：2026-08-31**
- **解决方式**：react-router-dom 从 7.18.1 升级到 7.18.2（同一 minor 的补丁，API 兼容），已清除该公告。
- **现状**：前端依赖经 npm install 后 npm audit 报 0 vulnerabilities；npm run audit:production 已从「仅放行该公告+时限例外」改为零容忍策略（任何 npm 公告即拦停发布门禁），并保留 BrowserRouter-only SPA 架构校验。
- **范围说明**：本应用是纯客户端 BrowserRouter SPA，不使用 RSC/Server Actions；此升级为防御性加固，不改变架构。
