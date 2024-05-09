# Skycaptain: Daggerverse
#
# TODO: Run checkout for caching in prepare step?
#
# SPDX-License-Identifier: BSD-3-Clause
#
from typing import Annotated, Callable, Self

import dagger
from dagger import Arg, Doc, dag, field, function, object_type

# TODO: Setup Renovate Bot to update tag and lock digest
DEFAULT_BASE_IMAGE_REF = "ghcr.io/siemens/kas/kas"

WORK_DIR = "/workdir"
SRC_DIR = WORK_DIR
REPO_REF_DIR = "/repos"
BUILD_DIR = f"{WORK_DIR}/build"

DL_DIR = f"{BUILD_DIR}/downloads"
SSTATE_DIR = f"{BUILD_DIR}/sstate-cache"

CACHE_CACHE_KEY = "kas-build-cache-cache"
DOWNLOADS_CACHE_KEY = "kas-build-downloads-cache"
SSTATE_CACHE_KEY = "kas-build-sstate-cache"
REPO_REF_CACHE_KEY = "kas-repo-ref-cache"

CommandArg = Annotated[str, Doc("Run command")]
ConfigArg = Annotated[str, Doc("Config file(s), separated by colon")]
ExtraBitbakeArgsArg = Annotated[list[str] | None, Doc("Extra arguments to pass to bitbake")]
ForceCheckoutArg = Annotated[
    bool,
    Doc(
        "Always checkout the desired commit/branch/tag of each repository, discarding any "
        "local changes"
    ),
]
FormatArg = Annotated[str, Arg(name="format"), Doc("Output format. Possible choices: yaml, json")]
IndentArg = Annotated[int, Doc("Line indent (# of spaces)")]
InplaceArg = Annotated[bool, Doc("Update lockfile in-place (requires –lock)")]
KeepConfigUnchangedArg = Annotated[bool, Doc("Skip steps that change the configuration")]
LockArg = Annotated[bool, Doc("Create lockfile with exact SHAs")]
PreserveEnvArg = Annotated[bool, Doc("Keep current user environment block")]
ResolveEnvArg = Annotated[bool, Doc("Set env defaults to captured env value")]
ResolveRefsArg = Annotated[bool, Doc("Replace floating refs with exact SHAs")]
SkipArgs = Annotated[list[str] | None, Doc("Skip build steps")]
TargetArg = Annotated[str | None, Doc("Target to built")]
TaskArg = Annotated[str | None, Doc("Task to run")]
UpdateArg = Annotated[
    bool,
    Doc(
        "Pull new upstream changes to the desired branch even if it is already checked out locally"
    ),
]

WithContainerFunc = Callable[[dagger.Container], dagger.Container]


@object_type
class Kas:
    base_ref: str = field(default=DEFAULT_BASE_IMAGE_REF)

    ctr: dagger.Container = field(init=False)
    src: dagger.Directory = field(default=dag.directory)

    netrc: dagger.Secret | None = None

    def __post_init__(self):
        self.ctr = self._base()

    # Properties -----------------------------------------------------------------------------------

    @function
    def container(self) -> dagger.Container:
        return self.ctr

    @function
    def with_container(self, ctr: dagger.Container) -> Self:
        self.ctr = ctr
        return self

    @function
    def source(self) -> dagger.Directory:
        return self.container().directory(SRC_DIR)

    @function
    def with_source(self, path: dagger.Directory) -> Self:
        self.src = path
        return self

    @function
    def with_netrc(self, path: dagger.Secret) -> Self:
        self.netrc = path
        return self

    # TODO: Append?
    @function
    def with_new_netrc(self, host: str, username: str, credential: dagger.Secret) -> Self:
        self.netrc = dag.secret(f"machine {host}\nlogin {username}\npassword {credential}")
        return self

    @function
    def deploy_dir(self) -> dagger.Directory:
        return dag.directory().with_directory(
            "/build",
            self.container().directory(BUILD_DIR),
            # TODO: This approach assumes a naming convention for multiconfig tmp directories. While
            # we use the most common conventions (see VSCode settings in upstream Poky), it could be
            # made more flexible by deep-searching deploy dirs and/or honouring TMPDIR.
            include=["tmp*/deploy/"],
        )

    # Functions ------------------------------------------------------------------------------------

    @function
    async def with_prepare(self) -> Self:
        return self.with_container(await self._prepare(self.container()))

    @function
    async def prepare(self) -> dagger.Container:
        return (await self.with_container(self._base()).with_prepare()).container()

    @function
    def with_exec(self, args: list[str]) -> Self:
        return self.with_container(self.container().with_exec(args))

    @function
    async def exec(self, args: list[str]) -> str:
        return await self.with_container(await self.prepare()).with_exec(args).container().stdout()

    @function
    def with_kas(self, args: list[str]) -> Self:
        return self.with_exec(["kas", *args])

    @function
    async def kas(self, args: list[str]) -> str:
        return await self.with_container(await self.prepare()).with_kas(args).container().stdout()

    @function
    def with_checkout(self, config: ConfigArg = ".config.yaml") -> Self:
        return self.with_kas(["checkout", "--force-checkout", "--update", config])

    @function
    async def checkout(self, config: ConfigArg = ".config.yaml") -> dagger.Directory:
        return (
            self.with_container(await self.prepare())
            .with_checkout(config)
            .container()
            .directory(SRC_DIR)
        )

    @function
    def with_dump(
        self,
        config: ConfigArg = ".config.yaml",
        skip: SkipArgs = None,
        force_checkout: ForceCheckoutArg = False,
        update: UpdateArg = False,
        format_: FormatArg = "yaml",
        indent: IndentArg = 4,
        resolve_refs: ResolveRefsArg = False,
        resolve_env: ResolveEnvArg = False,
        lock: LockArg = False,
        inplace: InplaceArg = False,
    ) -> Self:
        args = ["dump"]

        if skip is not None:
            args.extend(["--skip", *skip])

        if force_checkout:
            args.append("--force-checkout")

        if update:
            args.append("--update")

        args.extend(["--format", format_])

        if indent:
            args.extend(["--indent", str(indent)])

        if resolve_refs:
            args.append("--resolve-refs")

        if resolve_env:
            args.append("--resolve-env")

        if lock:
            args.append("--lock")

        if inplace:
            args.append("--inplace")

        args.append(config)

        return self.with_kas(args)

    @function
    async def dump(
        self,
        config: ConfigArg = ".config.yaml",
        skip: SkipArgs = None,
        force_checkout: ForceCheckoutArg = False,
        update: UpdateArg = False,
        format_: FormatArg = "yaml",
        indent: IndentArg = 4,
        resolve_refs: ResolveRefsArg = False,
        resolve_env: ResolveEnvArg = False,
        lock: LockArg = False,
    ) -> str:
        return await (
            self.with_container(await self.prepare())
            .with_dump(
                config=config,
                skip=skip,
                force_checkout=force_checkout,
                update=update,
                format_=format_,
                indent=indent,
                resolve_refs=resolve_refs,
                resolve_env=resolve_env,
                lock=lock,
            )
            .container()
            .stdout()
        )

    @function
    def with_build(
        self,
        config: ConfigArg = ".config.yaml",
        target: TargetArg = None,
        task: TaskArg = "build",
        extra_bitbake_args: ExtraBitbakeArgsArg = None,
    ) -> Self:
        args = ["build"]

        if target is not None:
            args.extend(["--target", target])

        args.extend(["--task", task])

        args.append(config)

        if extra_bitbake_args is not None and len(extra_bitbake_args) > 0:
            args.extend(["--", *extra_bitbake_args])

        return self.with_kas(args)

    @function
    async def build(
        self,
        config: ConfigArg = ".config.yaml",
        target: TargetArg = None,
        task: TaskArg = "build",
        extra_bitbake_args: ExtraBitbakeArgsArg = None,
    ) -> dagger.Directory:
        return (
            self.with_container(await self.prepare())
            .with_build(
                config,
                target=target,
                task=task,
                extra_bitbake_args=extra_bitbake_args,
            )
            .deploy_dir()
        )

    @function
    def with_shell(
        self,
        command: CommandArg,
        config: ConfigArg = ".config.yaml",
        force_checkout: ForceCheckoutArg = False,
        update: UpdateArg = False,
        preserve_env: PreserveEnvArg = False,
        keep_config_unchanged: KeepConfigUnchangedArg = False,
    ) -> Self:
        args = ["shell", "-c", command]

        if force_checkout:
            args.append("--force-checkout")

        if update:
            args.append("--update")

        if preserve_env:
            args.append("--preserve-env")

        if keep_config_unchanged:
            args.append("--keep-config-unchanged")

        args.append(config)

        return self.with_kas(args)

    @function
    async def shell(
        self,
        command: CommandArg,
        config: ConfigArg = ".config.yaml",
        force_checkout: ForceCheckoutArg = False,
        update: UpdateArg = False,
        preserve_env: PreserveEnvArg = False,
        keep_config_unchanged: KeepConfigUnchangedArg = False,
    ) -> dagger.Container:
        return (
            self.with_container(await self.prepare())
            .with_shell(
                command=command,
                config=config,
                force_checkout=force_checkout,
                update=update,
                preserve_env=preserve_env,
                keep_config_unchanged=keep_config_unchanged,
            )
            .container()
        )

    # Low-level functions --------------------------------------------------------------------------

    @function
    async def wipe_cache(self) -> str:
        return await self.exec(
            [
                "rm",
                "-rf",
                f"{BUILD_DIR}/cache/*",
                f"{BUILD_DIR}/downloads/*",
                f"{BUILD_DIR}/sstate-cache/*",
                f"{REPO_REF_DIR}/*",
            ]
        )

    # Internals ------------------------------------------------------------------------------------

    def _base(self) -> dagger.Container:
        return dag.container().from_(self.base_ref).without_entrypoint()

    async def _prepare(self, ctr: dagger.Container) -> dagger.Container:
        # Query the current non-root user. This expects the container to have a non-root user
        # installed and currently active
        non_root_user = await ctr.user()
        # We need to run a login shell to access the non-root user's home directory, because we
        # can't set USER or HOME globally in the container in case the user changes
        non_root_user_home = (await ctr.with_exec(["sh", "-c", "echo ${HOME}"]).stdout()).strip()

        # Setup project directory ---------------------------------------------

        ctr = (
            ctr.with_mounted_directory(SRC_DIR, self.src, owner=non_root_user)
            .with_env_variable("KAS_WORK_DIR", SRC_DIR)
            .with_workdir(SRC_DIR)
        )

        # Make Git trust any directory as otherwise git will refuse to run commands from the
        # non-root user. Requires Git 2.36 (Q2 2022). See https://stackoverflow.com/a/71940133
        ctr = ctr.with_exec(["git", "config", "--global", "--add", "safe.directory", "*"])

        # Setup build directory -----------------------------------------------

        ctr = (
            ctr.with_directory(
                BUILD_DIR,
                dag.directory()
                .with_new_directory(BUILD_DIR, permissions=0o755)
                .directory(BUILD_DIR),
                owner=non_root_user,
            )
            # OE-compatible env
            .with_env_variable("BUILDDIR", BUILD_DIR)
            # Kas-compatible env
            .with_env_variable("KAS_BUILD_DIR", BUILD_DIR)
        )

        # Setup cache mounts --------------------------------------------------

        # FIXME: When switching to another base image where the non-root-user has different UID/GID,
        # Bitbake will fail to access the files in cache directories. Consider to chown or add
        # function to clear the caches
        # TODO: download and sstate cache are sharable as all writes are atomic. Is it worth
        # blocking parallel builds for cache and repo ref?
        ctr = (
            ctr.with_mounted_cache(
                f"{BUILD_DIR}/cache",
                dag.cache_volume(CACHE_CACHE_KEY),
                sharing=dagger.CacheSharingMode.LOCKED,
                owner=non_root_user,
            )
            .with_mounted_cache(
                DL_DIR,
                dag.cache_volume(DOWNLOADS_CACHE_KEY),
                owner=non_root_user,
            )
            .with_env_variable("DL_DIR", DL_DIR)
            .with_mounted_cache(
                SSTATE_DIR,
                dag.cache_volume(SSTATE_CACHE_KEY),
                owner=non_root_user,
            )
            .with_env_variable("SSTATE_DIR", SSTATE_DIR)
            .with_mounted_cache(
                REPO_REF_DIR,
                dag.cache_volume(REPO_REF_CACHE_KEY),
                sharing=dagger.CacheSharingMode.LOCKED,
                owner=non_root_user,
            )
            .with_env_variable("KAS_REPO_REF_DIR", REPO_REF_DIR)
        )

        # Add credentials -----------------------------------------------------

        if self.netrc is not None:
            ctr = (
                ctr.with_mounted_secret(
                    f"{non_root_user_home}/.netrc",
                    self.netrc,
                    owner=non_root_user,
                    mode=0o600,
                )
                # GNU-compatible environment variable.
                # See https://www.gnu.org/software/inetutils/manual/html_node/The-_002enetrc-file.html
                .with_env_variable("NETRC", f"{non_root_user_home}/.netrc")
                # Kas-compatible environment variable.
                # See https://kas.readthedocs.io/en/latest/command-line.html#environment-variables
                .with_env_variable("NETRC_FILE", f"{non_root_user_home}/.netrc")
            )

        # Set defaults --------------------------------------------------------

        ctr = ctr.with_default_terminal_cmd(["/bin/bash"])

        return ctr
