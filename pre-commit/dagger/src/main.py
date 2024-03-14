# Skycaptain: Daggerverse
#
# SPDX-License-Identifier: BSD-3-Clause
#
from dataclasses import field

import dagger
from dagger import dag, function, object_type

# TODO: Use Renovate Bot to update tag and lock digest
DEFAULT_BASE_IMAGE = "alpine"

# TODO: Use Renovate Bot to update tag and lock digest
DEFAULT_PRE_COMMIT_VERSION = "3.6.2"


@object_type
class PreCommit:
    ctr: dagger.Container = field(init=False)
    src: dagger.Directory | None = field(default=None, init=False)

    pre_commit_version: str = field(default=DEFAULT_PRE_COMMIT_VERSION)

    def __post_init__(self):
        self.ctr = self.base()

    # Properties -----------------------------------------------------------------------------------

    @function
    def container(self) -> dagger.Container:
        return self.ctr

    @function
    def with_container(self, ctr: dagger.Container) -> "PreCommit":
        self.ctr = ctr
        return self

    @function
    def source(self) -> dagger.Directory:
        return self.container().directory("/src")

    @function
    def with_source(self, path: dagger.Directory) -> "PreCommit":
        self.src = path
        return self

    # Functions ------------------------------------------------------------------------------------

    @function
    def with_run(self, hook_stage: str | None = None) -> "PreCommit":
        return self.with_container(
            self.container.with_exec(self.get_command(hook_stage=hook_stage))
        )

    @function
    async def run(self, hook_stage: str | None = None) -> str:
        return await self.prepare().with_exec(self.get_command(hook_stage=hook_stage)).stdout()

    # Lower-level functions ------------------------------------------------------------------------

    @function
    def base(self) -> dagger.Container:
        return (
            dag.container()
            .from_(DEFAULT_BASE_IMAGE)
            # Install pre-commit's dependencies
            .with_exec(["apk", "add", "alpine-sdk", "python3", "python3-dev"])
            # Install pipx and pre-commit
            .with_env_variable("PIPX_HOME", "/opt/pipx")
            .with_env_variable("PIPX_BIN_DIR", "/usr/local/bin")
            .with_exec(["apk", "add", "--no-cache", "pipx"])
            .with_exec(["pipx", "install", f"pre-commit=={self.pre_commit_version}"])
        )

    # Internals ------------------------------------------------------------------------------------

    def get_command(self, hook_stage: str | None = None) -> list[str]:
        args = ["pre-commit", "run", "--all-files", "--verbose"]

        if hook_stage:
            args += ["--hook-stage", hook_stage]

        return args

    def prepare(self) -> dagger.Container:
        return (
            # See https://pre-commit.com/#managing-ci-caches
            self.ctr.with_mounted_cache(
                "/var/cache/xdg_cache_home/pre-commit",
                dag.cache_volume("pre-commit-home-cache"),
                sharing=dagger.CacheSharingMode.SHARED,
            )
            .with_env_variable("XDG_CACHE_HOME", "/var/cache/xdg_cache_home")
            .with_directory("/src", self.src)
            .with_workdir("/src")
        )
