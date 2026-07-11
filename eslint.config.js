export default [
  {
    ignores: ["**/node_modules/**", "**/.git/**"],
  },
  {
    files: ["static/**/*.js"],
    rules: {
      "no-undef": "warn",
      "no-unused-vars": "warn",
      "no-console": "off",
    },
  },
];
