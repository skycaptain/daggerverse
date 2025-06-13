# nooelint: oelint.var.mandatoryvar.SRC_URI
# Skycaptain: Daggerverse
#
# SPDX-License-Identifier: BSD-3-Clause
#
SUMMARY = "Daggerverse Minimal Recipe"
DESCRIPTION = "A minimal Daggerverse recipe for testing the kas module"
HOMEPAGE = "https://example.com/"
LICENSE = "BSD-3-Clause"

inherit nopackages

deltask do_compile
deltask do_configure
deltask do_create_runtime_spdx
deltask do_create_spdx
deltask do_fetch
deltask do_install
deltask do_package
deltask do_patch
deltask do_populate_sysroot
deltask do_unpack

EXCLUDE_FROM_WORLD = "1"
