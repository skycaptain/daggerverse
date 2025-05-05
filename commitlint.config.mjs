// Skycaptain: Daggerverse
//
// See https://commitlint.js.org for usage.
//
// SPDX-License-Identifier: BSD-3-Clause
//

/** @type {import('@commitlint/types').UserConfig} */
export default {
  extends: ["@commitlint/config-conventional"],
  ignores: [
    // Skip CI commits
    (message) => message.toLowerCase().includes("[skip ci]"),
    (message) => message.toLowerCase().includes("[ci skip]"),
    // Skip Renovate Bot messages, as dependency names often exceed the 100 character limit
    (message) => message.toLowerCase().includes("(deps): "),
  ],
};
