module.exports = {
  testEnvironment: 'node',
  testMatch: [
    '**/test_*.js',
    '**/*.test.js',
    '**/*.spec.js'
  ],
  collectCoverageFrom: [
    'auth.js',
    'billing.js',
    'chat.js',
    'server.js',
    'desktop/src/**/*.js',
    '!**/node_modules/**',
    '!**/vendor/**'
  ],
  coverageDirectory: 'coverage',
  coverageReporters: ['text', 'lcov', 'html'],
  testTimeout: 10000,
  verbose: true,
  errorOnDeprecated: true,
  forceExit: true,
  detectOpenHandles: true
};