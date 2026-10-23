import nextJest from "next/jest.js";

const createJestConfig = nextJest({
  dir: "./",
});

const customJestConfig = {
  moduleDirectories: ["node_modules", "<rootDir>/"],
  testEnvironment: "jest-environment-jsdom",
  moduleNameMapper: {
    "^@/(.*)$": "<rootDir>/$1",
    "\\.(css|less|scss|sass)$": "identity-obj-proxy",
  },
  testMatch: ["<rootDir>/app/**/*.test.{ts,tsx}", "<rootDir>/lib/**/*.test.{ts,tsx}"],
  collectCoverageFrom: [
    "<rootDir>/app/**/*.{ts,tsx}",
    "<rootDir>/lib/**/*.{ts,tsx}",
  ],
};

export default createJestConfig(customJestConfig);
