// Minimal, standard config wiring up the already-installed
// @typescript-eslint packages -- no ESLint config existed anywhere in
// this repo before (a pre-existing gap, not introduced by this
// batch), so `npm run lint` could never actually run. Deliberately
// conservative: recommended rule sets only, no opinionated additions,
// since introducing strict/stylistic rules now would flag pre-existing
// code across the whole app that's out of scope for this batch.
module.exports = {
  root: true,
  env: { browser: true, es2021: true, node: true },
  extends: ["eslint:recommended", "plugin:@typescript-eslint/recommended", "plugin:react-hooks/recommended"],
  parser: "@typescript-eslint/parser",
  parserOptions: { ecmaVersion: "latest", sourceType: "module", ecmaFeatures: { jsx: true } },
  plugins: ["@typescript-eslint", "react-hooks"],
  ignorePatterns: ["dist", "node_modules", "*.config.*"],
  rules: {
    "@typescript-eslint/no-unused-vars": ["warn", { argsIgnorePattern: "^_" }],
    "@typescript-eslint/no-explicit-any": "off",
    "no-undef": "off", // TypeScript itself already catches this; avoids false positives on browser/JSX globals
  },
};
