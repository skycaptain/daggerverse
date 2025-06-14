# Skycaptain: Daggerverse
#
# SPDX-License-Identifier: BSD-3-Clause
#
from datetime import datetime
from typing import Annotated, Self

import dagger
from dagger import Doc, Name, dag, field, function, object_type

DEFAULT_BASE_IMAGE_REF = "ghcr.io/siemens/kas/kas:4.8"

KAS_WORK_DIR = "/workdir"
KAS_REPO_REF_DIR = "/repos"
KAS_BUILD_DIR = "/build"

DL_DIR = "/downloads"
SSTATE_DIR = "/sstate-cache"

CACHE_CACHE_KEY = "cache-cache"
DOWNLOADS_CACHE_KEY = "downloads-cache"
SSTATE_CACHE_KEY = "sstate-cache"
REPO_REF_CACHE_KEY = "repo-ref-cache"

DUMP_STDOUT_FILEPATH = "/tmp/.daggerverse-kas-dump-stdout"
LOCK_STDOUT_FILEPATH = "/tmp/.daggerverse-kas-lock-stdout"

GITCONFIG_FILE = "/tmp/.daggerverse-kas-gitconfig"

CommandDoc = Doc("Command to run")
ConfigDoc = Doc("Configuration file(s)")
ExpandDoc = Doc("Expand environment variables in arguments")
ExpectDoc = Doc("Expected return type")
ExtraArgsDoc = Doc("Additional command arguments")
ExtraBitbakeArgsDoc = Doc("Extra arguments to pass to bitbake")
ExtraEnvVariablesDoc = Doc("Additional environment variables (KEY=VALUE format)")
ForceCheckoutDoc = Doc("Always checkout desired commit/branch/tag, discarding local changes")
FormatDoc = Doc("Output format (yaml or json)")
KeepConfigUnchangedDoc = Doc("Skip steps that change the configuration")
LockDoc = Doc("Create lockfile with exact SHAs")
NetrcDoc = Doc("Netrc file for authentication")
PreserveEnvDoc = Doc("Keep current user environment block")
ResolveEnvDoc = Doc("Set environment defaults to captured environment values")
ResolveLocalDoc = Doc("Add tracking information of root repository")
ResolveRefsDoc = Doc("Replace floating refs with exact SHAs")
SrcDoc = Doc("Source directory")
TargetDoc = Doc("Target to build")
TaskDoc = Doc("Task to run")
UpdateDoc = Doc("Pull upstream changes to the branch even if already checked out")


def format_config_arg(configs: list[str]) -> str:
    return ":".join(configs)


@object_type
class Kas:
    base_image_ref: Annotated[str, Doc("Base container image reference")] = DEFAULT_BASE_IMAGE_REF

    ctr: Annotated[dagger.Container, Doc("Container instance")] = field(init=False)
    src: Annotated[dagger.Directory, SrcDoc] = field(default=dag.directory)

    netrc: Annotated[dagger.Secret | None, NetrcDoc] = None

    def __post_init__(self):
        self.ctr = self._base()

    # Properties -----------------------------------------------------------------------------------

    @function
    def container(self) -> dagger.Container:
        return self.ctr

    @function
    def with_container(self, ctr: Annotated[dagger.Container, Doc("Container to use")]) -> Self:
        self.ctr = ctr
        return self

    @function
    def source(self) -> dagger.Directory:
        return self.container().directory(KAS_WORK_DIR)

    @function
    def with_source(self, path: Annotated[dagger.Directory, SrcDoc]) -> Self:
        self.src = path
        return self

    @function
    def with_netrc(self, path: Annotated[dagger.Secret, NetrcDoc]) -> Self:
        self.netrc = path
        return self

    @function
    def build_dir(self) -> dagger.Directory:
        return self.container().directory(KAS_BUILD_DIR)

    # Functions ------------------------------------------------------------------------------------

    @function
    async def with_prepare(
        self,
        extra_env_variables: Annotated[list[str] | None, ExtraEnvVariablesDoc] = None,
    ) -> Self:
        ctr = self.container()

        # Query the current non-root user. This expects the container to have a non-root user
        # installed and currently active
        non_root_user = await ctr.user()

        # Add credentials -----------------------------------------------------

        if self.netrc is not None:
            ctr = ctr.with_mounted_secret(
                "/run/secrets/NETRC_FILE",
                self.netrc,
                owner=non_root_user,
                mode=0o600,
            ).with_env_variable("NETRC_FILE", "/run/secrets/NETRC_FILE")

        # Setup gitconfig -----------------------------------------------------

        # Make Git trust any directory as otherwise git will refuse to run commands from the
        # non-root user. Requires Git 2.36 (Q2 2022). See https://stackoverflow.com/a/71940133
        # Using git-config instead of plain file to allow for easier extension in other modules
        ctr = ctr.with_env_variable("GITCONFIG_FILE", GITCONFIG_FILE).with_exec(
            ["git", "config", "--file", "${GITCONFIG_FILE}", "--add", "safe.directory", "*"],
            expand=True,
        )

        # Setup build directory -----------------------------------------------

        ctr = (
            # Using mounted directory so that the build dir is not stored in the container.
            # See https://github.com/dagger/dagger/discussions/6688
            ctr.with_mounted_directory(
                KAS_BUILD_DIR,
                dag.directory()
                .with_new_directory(KAS_BUILD_DIR, permissions=0o755)
                .directory(KAS_BUILD_DIR),
                owner=non_root_user,
            )
            # Kas-compatible env
            .with_env_variable("KAS_BUILD_DIR", KAS_BUILD_DIR)
        )

        # Setup cache mounts --------------------------------------------------

        ctr = (
            ctr.with_mounted_cache(
                KAS_REPO_REF_DIR,
                dag.cache_volume(REPO_REF_CACHE_KEY, namespace="kas"),
                sharing=dagger.CacheSharingMode.PRIVATE,
                owner=non_root_user,
            )
            .with_env_variable("KAS_REPO_REF_DIR", KAS_REPO_REF_DIR)
            .with_mounted_cache(
                f"{KAS_BUILD_DIR}/cache",
                dag.cache_volume(CACHE_CACHE_KEY, namespace="kas"),
                sharing=dagger.CacheSharingMode.PRIVATE,
                owner=non_root_user,
            )
            .with_mounted_cache(
                DL_DIR,
                dag.cache_volume(DOWNLOADS_CACHE_KEY, namespace="kas"),
                owner=non_root_user,
            )
            .with_env_variable("DL_DIR", DL_DIR)
            .with_mounted_cache(
                SSTATE_DIR,
                dag.cache_volume(SSTATE_CACHE_KEY, namespace="kas"),
                owner=non_root_user,
            )
            .with_env_variable("SSTATE_DIR", SSTATE_DIR)
        )

        # Setup project directory ---------------------------------------------

        # Add the project directory last to improve caching
        ctr = (
            ctr.with_env_variable("KAS_WORK_DIR", KAS_WORK_DIR)
            .with_mounted_directory(KAS_WORK_DIR, self.src, owner=non_root_user)
            .with_workdir(KAS_WORK_DIR)
        )

        # Add optional env variables ------------------------------------------

        if extra_env_variables is not None:
            for env_variable in extra_env_variables:
                key, value = env_variable.split("=", 1)
                ctr = ctr.with_env_variable(key, value)

        return self.with_container(ctr)

    @function
    async def prepare(
        self,
        src: Annotated[dagger.Directory, SrcDoc],
        extra_env_variables: Annotated[list[str] | None, ExtraEnvVariablesDoc] = None,
    ) -> dagger.Container:
        ctr = (
            await self.with_container(self._base())
            .with_source(src)
            .with_prepare(extra_env_variables=extra_env_variables)
        ).container()

        # Set the result as the current container to ease subsequent calls
        return self.with_container(ctr).container()

    @function
    def with_exec(
        self,
        args: Annotated[list[str], Doc("Command arguments to execute")],
        *,
        redirect_stdout: Annotated[str | None, Doc("File path to redirect stdout")] = "",
        redirect_stderr: Annotated[str | None, Doc("File path to redirect stderr")] = "",
        expand: Annotated[bool | None, ExpandDoc] = False,
        expect: Annotated[dagger.ReturnType | None, ExpectDoc] = dagger.ReturnType.SUCCESS,
        use_entrypoint: Annotated[bool, Doc("Use container entrypoint")] = False,
    ) -> Self:
        ctr = self.container().with_exec(
            args,
            redirect_stdout=redirect_stdout,
            redirect_stderr=redirect_stderr,
            expand=expand,
            expect=expect,
            use_entrypoint=use_entrypoint,
        )

        return self.with_container(ctr)

    @function
    async def exec(
        self,
        src: Annotated[dagger.Directory, SrcDoc],
        args: Annotated[list[str], Doc("Command arguments to execute")],
        *,
        redirect_stdout: Annotated[str | None, Doc("File path to redirect stdout")] = "",
        redirect_stderr: Annotated[str | None, Doc("File path to redirect stderr")] = "",
        expand: Annotated[bool | None, ExpandDoc] = False,
        use_entrypoint: Annotated[bool, Doc("Use container entrypoint")] = False,
        extra_env_variables: Annotated[list[str] | None, ExtraEnvVariablesDoc] = None,
    ) -> str:
        await self.prepare(src=src, extra_env_variables=extra_env_variables)

        ctr = self.with_exec(
            args,
            redirect_stdout=redirect_stdout,
            redirect_stderr=redirect_stderr,
            expand=expand,
            use_entrypoint=use_entrypoint,
        ).container()

        return await ctr.stdout()

    @function
    def with_env_variable(
        self,
        key: str,
        value: str,
        *,
        expand: Annotated[bool | None, ExpandDoc] = False,
    ) -> Self:
        ctr = self.container().with_env_variable(key, value, expand=expand)
        return self.with_container(ctr)

    @function
    def with_invalidate_layer_cache(self) -> Self:
        return self.with_env_variable("DAGGERVERSE_KAS_CACHE_BUSTER", str(datetime.now()))

    @function
    def with_kas(
        self,
        args: Annotated[list[str], Doc("Kas command arguments")],
        *,
        redirect_stdout: Annotated[str | None, Doc("File path to redirect stdout")] = "",
        redirect_stderr: Annotated[str | None, Doc("File path to redirect stderr")] = "",
        expand: Annotated[bool | None, ExpandDoc] = False,
        expect: Annotated[dagger.ReturnType | None, ExpectDoc] = dagger.ReturnType.SUCCESS,
    ) -> Self:
        return self.with_exec(
            args,
            redirect_stdout=redirect_stdout,
            redirect_stderr=redirect_stderr,
            expand=expand,
            expect=expect,
            use_entrypoint=True,
        )

    @function
    async def kas(
        self,
        src: Annotated[dagger.Directory, SrcDoc],
        args: Annotated[list[str], Doc("Kas command arguments")],
        *,
        redirect_stdout: Annotated[str | None, Doc("File path to redirect stdout")] = "",
        redirect_stderr: Annotated[str | None, Doc("File path to redirect stderr")] = "",
        expand: Annotated[bool | None, ExpandDoc] = False,
        extra_env_variables: Annotated[list[str] | None, ExtraEnvVariablesDoc] = None,
    ) -> str:
        await self.prepare(src=src, extra_env_variables=extra_env_variables)

        ctr = self.with_kas(
            args,
            redirect_stdout=redirect_stdout,
            redirect_stderr=redirect_stderr,
            expand=expand,
        ).container()

        return await ctr.stdout()

    @function
    def with_checkout(
        self,
        configs: Annotated[list[str] | None, Name("config"), ConfigDoc] = None,
        *,
        force_checkout: Annotated[bool, ForceCheckoutDoc] = False,
        update: Annotated[bool, UpdateDoc] = False,
        extra_args: Annotated[list[str] | None, ExtraArgsDoc] = None,
    ) -> Self:
        args = ["checkout"]

        if force_checkout:
            args.append("--force-checkout")

        if update:
            args.append("--update")

        args.extend(extra_args or [])

        if configs is not None:
            args.append(format_config_arg(configs))

        return self.with_kas(args)

    @function
    async def checkout(
        self,
        src: Annotated[dagger.Directory, SrcDoc],
        configs: Annotated[list[str] | None, Name("config"), ConfigDoc] = None,
        *,
        force_checkout: Annotated[bool, ForceCheckoutDoc] = False,
        update: Annotated[bool, UpdateDoc] = False,
        extra_args: Annotated[list[str] | None, ExtraArgsDoc] = None,
        extra_env_variables: Annotated[list[str] | None, ExtraEnvVariablesDoc] = None,
    ) -> dagger.Directory:
        await self.prepare(src=src, extra_env_variables=extra_env_variables)

        src = self.with_checkout(
            configs,
            force_checkout=force_checkout,
            update=update,
            extra_args=extra_args,
        ).source()

        return await src.sync()

    @function
    def with_dump(
        self,
        configs: Annotated[list[str] | None, Name("config"), ConfigDoc] = None,
        *,
        force_checkout: Annotated[bool, ForceCheckoutDoc] = False,
        update: Annotated[bool, UpdateDoc] = False,
        format_: Annotated[str, Name("format"), FormatDoc] = "yaml",
        resolve_refs: Annotated[bool, ResolveRefsDoc] = False,
        resolve_local: Annotated[bool, ResolveLocalDoc] = False,
        resolve_env: Annotated[bool, ResolveEnvDoc] = False,
        extra_args: Annotated[list[str] | None, ExtraArgsDoc] = None,
    ) -> "WithDumpResult":
        args = ["dump"]

        if force_checkout:
            args.append("--force-checkout")

        if update:
            args.append("--update")

        args.extend(["--format", format_])

        if resolve_refs:
            args.append("--resolve-refs")

        if resolve_local:
            args.append("--resolve-local")

        if resolve_env:
            args.append("--resolve-env")

        args.extend(extra_args or [])

        if configs is not None:
            args.append(format_config_arg(configs))

        ctr = self.with_kas(args, redirect_stdout=DUMP_STDOUT_FILEPATH).container()

        return WithDumpResult(kas=self, result=ctr.file(DUMP_STDOUT_FILEPATH))  # type: ignore

    @function
    async def dump(
        self,
        src: Annotated[dagger.Directory, SrcDoc],
        configs: Annotated[list[str] | None, Name("config"), ConfigDoc] = None,
        *,
        force_checkout: Annotated[bool, ForceCheckoutDoc] = False,
        update: Annotated[bool, UpdateDoc] = False,
        format_: Annotated[str, Name("format"), FormatDoc] = "yaml",
        resolve_refs: Annotated[bool, ResolveRefsDoc] = False,
        resolve_local: Annotated[bool, ResolveLocalDoc] = False,
        resolve_env: Annotated[bool, ResolveEnvDoc] = False,
        extra_args: Annotated[list[str] | None, ExtraArgsDoc] = None,
        extra_env_variables: Annotated[list[str] | None, ExtraEnvVariablesDoc] = None,
        # Not implementing inplace as it does not make sense for a CLI function
    ) -> dagger.File:
        await self.prepare(src=src, extra_env_variables=extra_env_variables)

        with_dump_result = self.with_dump(
            configs=configs,
            force_checkout=force_checkout,
            update=update,
            format_=format_,
            resolve_refs=resolve_refs,
            resolve_local=resolve_local,
            resolve_env=resolve_env,
            extra_args=extra_args,
        )

        return with_dump_result.result

    @function
    def with_build(
        self,
        configs: Annotated[list[str] | None, Name("config"), ConfigDoc] = None,
        *,
        extra_bitbake_args: Annotated[list[str] | None, ExtraBitbakeArgsDoc] = None,
        force_checkout: Annotated[bool, ForceCheckoutDoc] = False,
        update: Annotated[bool, UpdateDoc] = False,
        keep_config_unchanged: Annotated[bool, KeepConfigUnchangedDoc] = False,
        target: Annotated[str | None, TargetDoc] = None,
        task: Annotated[str | None, TaskDoc] = None,
        extra_args: Annotated[list[str] | None, ExtraArgsDoc] = None,
        expect: Annotated[dagger.ReturnType | None, ExpectDoc] = dagger.ReturnType.SUCCESS,
    ) -> Self:
        args = ["build"]

        if force_checkout:
            args.append("--force-checkout")

        if update:
            args.append("--update")

        if keep_config_unchanged:
            args.append("--keep-config-unchanged")

        if target is not None:
            args.extend(["--target", target])

        if task is not None:
            args.extend(["--task", task])

        args.extend(extra_args or [])

        if configs is not None:
            args.append(format_config_arg(configs))

        if extra_bitbake_args:
            args.extend(["--", *extra_bitbake_args])

        return self.with_kas(args, expect=expect)

    @function
    async def build(
        self,
        src: Annotated[dagger.Directory, SrcDoc],
        configs: Annotated[list[str] | None, Name("config"), ConfigDoc] = None,
        *,
        extra_bitbake_args: Annotated[list[str] | None, ExtraBitbakeArgsDoc] = None,
        force_checkout: Annotated[bool, ForceCheckoutDoc] = False,
        update: Annotated[bool, UpdateDoc] = False,
        keep_config_unchanged: Annotated[bool, KeepConfigUnchangedDoc] = False,
        target: Annotated[str | None, TargetDoc] = None,
        task: Annotated[str | None, TaskDoc] = "build",
        extra_args: Annotated[list[str] | None, ExtraArgsDoc] = None,
        extra_env_variables: Annotated[list[str] | None, ExtraEnvVariablesDoc] = None,
    ) -> dagger.Directory:
        await self.prepare(src=src, extra_env_variables=extra_env_variables)

        build_dir = self.with_build(
            configs,
            extra_bitbake_args=extra_bitbake_args,
            force_checkout=force_checkout,
            update=update,
            keep_config_unchanged=keep_config_unchanged,
            target=target,
            task=task,
            extra_args=extra_args,
        ).build_dir()

        return await build_dir.sync()

    @function
    def with_shell(
        self,
        configs: Annotated[list[str] | None, Name("config"), ConfigDoc] = None,
        *,
        command: Annotated[str, CommandDoc],
        force_checkout: Annotated[bool, ForceCheckoutDoc] = False,
        update: Annotated[bool, UpdateDoc] = False,
        preserve_env: Annotated[bool, PreserveEnvDoc] = False,
        keep_config_unchanged: Annotated[bool, KeepConfigUnchangedDoc] = False,
        extra_args: Annotated[list[str] | None, ExtraArgsDoc] = None,
        expand: Annotated[bool | None, ExpandDoc] = False,
        expect: Annotated[dagger.ReturnType | None, ExpectDoc] = dagger.ReturnType.SUCCESS,
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

        args.extend(extra_args or [])

        if configs is not None:
            args.append(format_config_arg(configs))

        return self.with_kas(args, expand=expand, expect=expect)

    @function
    async def shell(
        self,
        src: Annotated[dagger.Directory, SrcDoc],
        configs: Annotated[list[str] | None, Name("config"), ConfigDoc] = None,
        *,
        command: Annotated[str, CommandDoc],
        force_checkout: Annotated[bool, ForceCheckoutDoc] = False,
        update: Annotated[bool, UpdateDoc] = False,
        preserve_env: Annotated[bool, PreserveEnvDoc] = False,
        keep_config_unchanged: Annotated[bool, KeepConfigUnchangedDoc] = False,
        extra_args: Annotated[list[str] | None, ExtraArgsDoc] = None,
        expand: Annotated[bool | None, ExpandDoc] = False,
        extra_env_variables: Annotated[list[str] | None, ExtraEnvVariablesDoc] = None,
    ) -> dagger.Container:
        await self.prepare(src=src, extra_env_variables=extra_env_variables)

        ctr = self.with_shell(
            command=command,
            configs=configs,
            force_checkout=force_checkout,
            update=update,
            preserve_env=preserve_env,
            keep_config_unchanged=keep_config_unchanged,
            extra_args=extra_args,
            expand=expand,
        ).container()

        return ctr

    @function
    def with_for_all_repos(
        self,
        configs: Annotated[list[str] | None, Name("config"), ConfigDoc] = None,
        *,
        command: Annotated[str, CommandDoc],
        extra_args: Annotated[list[str] | None, ExtraArgsDoc] = None,
        expand: Annotated[bool | None, ExpandDoc] = False,
        expect: Annotated[dagger.ReturnType | None, ExpectDoc] = dagger.ReturnType.SUCCESS,
    ) -> Self:
        args = ["for-all-repos", *(extra_args or [])]

        if configs is not None:
            args.append(format_config_arg(configs))

        args.append(command)

        return self.with_kas(args, expand=expand, expect=expect)

    @function
    async def for_all_repos(
        self,
        src: Annotated[dagger.Directory, SrcDoc],
        configs: Annotated[list[str] | None, Name("config"), ConfigDoc] = None,
        *,
        command: Annotated[str, CommandDoc],
        extra_args: Annotated[list[str] | None, ExtraArgsDoc] = None,
        expand: Annotated[bool | None, ExpandDoc] = False,
        extra_env_variables: Annotated[list[str] | None, ExtraEnvVariablesDoc] = None,
    ) -> dagger.Container:
        await self.prepare(src=src, extra_env_variables=extra_env_variables)

        ctr = self.with_for_all_repos(
            configs=configs,
            command=command,
            extra_args=extra_args,
            expand=expand,
        ).container()

        return ctr

    @function
    def with_lock(
        self,
        configs: Annotated[list[str] | None, Name("config"), ConfigDoc] = None,
        *,
        force_checkout: Annotated[bool, ForceCheckoutDoc] = False,
        update: Annotated[bool, UpdateDoc] = False,
        extra_args: Annotated[list[str] | None, ExtraArgsDoc] = None,
    ) -> "WithLockResult":
        args = ["lock"]

        if force_checkout:
            args.append("--force-checkout")

        if update:
            args.append("--update")

        args.extend(extra_args or [])

        if configs is not None:
            args.append(format_config_arg(configs))

        ctr = self.with_kas(args, redirect_stdout=LOCK_STDOUT_FILEPATH).container()

        return WithLockResult(kas=self, result=ctr.file(LOCK_STDOUT_FILEPATH))  # type: ignore

    @function
    async def lock(
        self,
        src: Annotated[dagger.Directory, SrcDoc],
        configs: Annotated[list[str] | None, Name("config"), ConfigDoc] = None,
        *,
        force_checkout: Annotated[bool, ForceCheckoutDoc] = False,
        update: Annotated[bool, UpdateDoc] = False,
        extra_args: Annotated[list[str] | None, ExtraArgsDoc] = None,
        extra_env_variables: Annotated[list[str] | None, ExtraEnvVariablesDoc] = None,
    ) -> dagger.File:
        await self.prepare(src=src, extra_env_variables=extra_env_variables)

        with_lock_result = self.with_lock(
            configs=configs,
            force_checkout=force_checkout,
            update=update,
            extra_args=extra_args,
        )

        return with_lock_result.result

    # Internals ------------------------------------------------------------------------------------

    def _base(self) -> dagger.Container:
        return (
            dag.container()
            .from_(self.base_image_ref)
            .with_entrypoint(["kas"])
            .with_default_terminal_cmd(["/bin/bash"])
        )


@object_type
class WithDumpResult:
    kas: Annotated[Kas, Doc("Kas instance")] = field()
    result: Annotated[dagger.File, Doc("Dump output file")] = field()


@object_type
class WithLockResult:
    kas: Annotated[Kas, Doc("Kas instance")] = field()
    result: Annotated[dagger.File, Doc("Lock file output")] = field()
