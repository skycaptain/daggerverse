# Skycaptain: Daggerverse
#
# SPDX-License-Identifier: BSD-3-Clause
#
import json

import dagger
from dagger import ReturnType, dag, field, function, object_type


@object_type
class Tests:
    prebuilt_caches_ctr: dagger.Container = field(default=dag.container)

    @function
    async def all(self):
        await self.test_prepare()
        await self.test_kas()
        await self.test_checkout()
        await self.test_dump()
        await self.test_build()
        await self.test_shell()

    # Tests ----------------------------------------------------------------------------------------

    @function
    async def test_prepare(self):
        src = self.get_src()
        ctr = await dag.kas().prepare(src)

        # Check if kas is installed and executable
        cmd = await ctr.with_exec(["kas", "--version"], expect=ReturnType.ANY)
        actual_exit_code = await cmd.exit_code()
        assert actual_exit_code == 0, "kas command not found or not executable"

        # Check container runs as non-root user
        actual_user = await ctr.user()
        assert actual_user != "root", "Container should not run as root user"

    @function
    async def test_kas(self):
        src = self.get_src()
        result = await dag.kas().kas(src, args=["--version"])

        # Check if result is not empty
        assert result != "", "kas command returned empty result"

    @function
    async def test_checkout(self):
        src = self.get_src()
        source_dir = await dag.kas().checkout(src, config=["test_poky.yml"])

        # Check if source_dir is not empty and contains expected files
        actual_entries = await source_dir.entries()
        assert len(actual_entries) > 0, "Result should not be empty"
        assert "poky/" in actual_entries, "Result should contain 'poky' directory"
        assert "test_poky.yml" in actual_entries, "Result should contain 'test_poky.yml' file"

    @function
    async def test_dump(self):
        src = self.get_src()
        result = await dag.kas().dump(src, config=["test_poky.yml"], format="json")

        # Check if result is not empty
        actual_contents = await result.contents()
        assert result != "", "kas dump command returned empty result"

        # Check if result is valid JSON
        actual_contents = await result.contents()
        try:
            json.loads(actual_contents)
        except json.JSONDecodeError:
            assert False, "kas dump command returned invalid JSON"

    @function
    async def test_build(self):
        src = self.get_src()
        build_dir = dag.kas().build(src, config=["test_poky.yml"])

        entries = await build_dir.entries()

        assert "tmp/" in entries, "Build directory should contain 'tmp' directory"

    @function
    async def test_shell(self):
        src = self.get_src()
        ctr = await dag.kas().shell(src, config=["test_poky.yml"], command="ls")

        # Check if the command executed successfully
        actual_result = await ctr.stdout()
        assert actual_result != "", "Command returned empty result"

    # Internal -------------------------------------------------------------------------------------

    def get_src(self) -> dagger.Directory:
        """
        Get the source directory for the tests.
        """
        return dag.current_module().source().directory("./fixtures")
