/**
 * 部署配置文件 - 从环境变量读取敏感信息
 * 
 * 使用方法：
 *   1. 设置环境变量: set DEPLOY_PASS=你的新密码 （Windows CMD）
 *      或 export DEPLOY_PASS=你的新密码 （Git Bash）
 *   2. 引入: const { DEPLOY_PASS, DEPLOY_HOST, DEPLOY_USER } = require('./deploy-config');
 *   3. 使用: { host: DEPLOY_HOST, username: DEPLOY_USER, password: DEPLOY_PASS }
 */
const DEPLOY_HOST = '120.79.17.184';
const DEPLOY_USER = 'root';
const DEPLOY_PASS = process.env.DEPLOY_PASS;  // 必须从环境变量读取，不设默认值！
if (!DEPLOY_PASS) {
  console.warn('⚠️  警告: 未设置 DEPLOY_PASS 环境变量！部署脚本将无法连接服务器。');
}

module.exports = { DEPLOY_HOST, DEPLOY_USER, DEPLOY_PASS };
