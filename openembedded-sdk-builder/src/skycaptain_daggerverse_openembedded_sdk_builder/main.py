# Skycaptain: Daggerverse
#
# SPDX-License-Identifier: BSD-3-Clause
#
from typing import Self

import dagger
from dagger import dag, field, function, object_type

# FIXME: Add Renovate configuration to lock and update the digests of the refs.
# See https://github.com/renovatebot/renovate/issues/10993
DEFAULT_BUILDER_IMAGE_REF = "python:3.13-bookworm"
DEFAULT_BASE_IMAGE_REF = "mcr.microsoft.com/devcontainers/cpp:bookworm"

SDK_INSTALL_DIR = "/sdk"


@object_type
class OpenembeddedSdkBuilder:
    base_image_ref: str = DEFAULT_BASE_IMAGE_REF

    sdk_dir: dagger.Directory = field(default=dag.directory)

    entrypoint: dagger.File = field(
        default=lambda: dag.file(
            "entrypoint",
            r"""#!/bin/sh
# Source the environment setup file
. "$(find "${SDK_HOME}" -maxdepth 1 -type f -name 'environment-setup-*')"

# Execute CMD
exec "$@"
""",
            permissions=0o755,
        )
    )

    @function
    async def with_sdk_dir_from_deploy_bin_ref(
        self,
        ref: str,
        *,
        builder_image_ref: str = DEFAULT_BUILDER_IMAGE_REF,
        platform: dagger.Platform | None = None,
    ) -> Self:
        return await self.with_sdk_dir_from_deploy_bin_ctr(
            ctr=dag.container(platform=platform).from_(ref),
            builder_image_ref=builder_image_ref,
            platform=platform,
        )

    @function
    async def with_sdk_dir_from_deploy_bin_ctr(
        self,
        ctr: dagger.Container,
        *,
        builder_image_ref: str = DEFAULT_BUILDER_IMAGE_REF,
        platform: dagger.Platform | None = None,
    ) -> Self:
        return await self.with_sdk_dir_from_deploy_bin_dir(
            directory=ctr.directory("/"),
            platform=platform or await ctr.platform(),
            builder_image_ref=builder_image_ref,
        )

    @function
    async def with_sdk_dir_from_deploy_bin_dir(
        self,
        directory: dagger.Directory,
        *,
        builder_image_ref: str = DEFAULT_BUILDER_IMAGE_REF,
        platform: dagger.Platform | None = None,
    ) -> Self:
        # Find the toolchain installer script in the binaries directory
        sdk_installer_path = await directory.glob("**/tmp*/deploy/sdk/*toolchain*.sh")

        if len(sdk_installer_path) != 1:
            raise ValueError(f"Expected exactly one SDK installer, found {len(sdk_installer_path)}")

        self.sdk_dir = (
            dag.container(platform=platform)
            .from_(builder_image_ref)
            .with_mounted_directory("/src", directory)
            .with_exec([f"/src/{sdk_installer_path}", "-d", SDK_INSTALL_DIR, "-y"])
            .directory(SDK_INSTALL_DIR)
        )

        return self

    @function
    async def container(self, platform: dagger.Platform | None = None) -> dagger.Container:
        ctr = dag.container(platform=platform).from_(self.base_image_ref)

        # Copy the SDK from the builder container
        ctr = (
            ctr
            # Add the installed SDK directory
            .with_directory(SDK_INSTALL_DIR, self.sdk_dir)
            # Add entrypoint
            .with_file("/usr/bin/entrypoint", self.entrypoint, permissions=0o755)
            .with_entrypoint(["/usr/bin/entrypoint"])
            # The default command when running the container
            .with_default_args(["/bin/bash"])
            # Export the location of the installed SDK for downstream scripts
            .with_env_variable("SDK_HOME", SDK_INSTALL_DIR)
        )

        # Bake-in OECORE_NATIVE_SYSROOT to make native SDK tools available without executing the
        # environment setup script, e.g., when using with a devcontainer
        oe_native_sysroot = (
            await ctr.with_exec(
                ["printenv", "OECORE_NATIVE_SYSROOT"],
                use_entrypoint=True,
            ).stdout()
        ).strip()
        if not oe_native_sysroot:
            raise ValueError("OECORE_NATIVE_SYSROOT environment variable not found in the SDK")

        ctr = ctr.with_env_variable("OECORE_NATIVE_SYSROOT", oe_native_sysroot)

        # Find and bake-in the environment setup script, e.g. to ease running tasks in VS Code
        env_setup = await ctr.directory(SDK_INSTALL_DIR).glob("environment-setup-*")
        if len(env_setup) != 1:
            raise ValueError(f"Expected exactly one env setup script, found {len(env_setup)}")

        ctr = ctr.with_env_variable("SDK_ENV_SETUP", f"{SDK_INSTALL_DIR}/{env_setup[0]}")

        return ctr
