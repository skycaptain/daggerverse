// Skycaptain: Daggerverse
//
// See https://semantic-release.gitbook.io/ for usage.
//
// SPDX-License-Identifier: BSD-3-Clause
//
// RELEASE BUSTER: 0
//
const packageName = "openembedded-sdk-builder";

/** @type {import('semantic-release').GlobalConfig} */
export default {
  extends: "semantic-release-monorepo",
  plugins: [
    "@semantic-release/commit-analyzer",
    "@semantic-release/release-notes-generator",
    "@semantic-release/github",
  ],
  preset: "conventionalcommits",
  tagFormat: `${packageName}-v\${version}`,
};
