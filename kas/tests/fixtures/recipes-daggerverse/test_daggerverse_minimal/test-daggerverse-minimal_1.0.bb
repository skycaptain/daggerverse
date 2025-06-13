# Skycaptain: Daggerverse
#
# SPDX-License-Identifier: BSD-3-Clause
#
SUMMARY = "Daggerverse Minimal Recipe"
DESCRIPTION = "A minimal Daggerverse recipe for testing the kas module"
HOMEPAGE = "https://example.com/"
LICENSE = "BSD-3-Clause"

inherit allarch

do_configure[noexec] = "1"
do_compile[noexec] = "1"
do_install[noexec] = "1"

EXCLUDE_FROM_WORLD = "1"
